"""Sites, alert policies, audit log, and notification outbox.

Policy evaluation runs on stored events. It does not require a YOLO model.
Outbox rows are marked sent locally — nothing is posted to the public internet.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    Alert,
    AlertPolicy,
    AuditLog,
    Camera,
    Event,
    NotificationOutbox,
    Site,
    utcnow,
)

RULE_ZONE_AFTER_HOURS = "zone_after_hours"
RULE_LOITERING = "loitering"
RULE_UNKNOWN_FACE = "unknown_face"
RULE_TYPES = {RULE_ZONE_AFTER_HOURS, RULE_LOITERING, RULE_UNKNOWN_FACE}

DEFAULT_CONFIG = {
    RULE_ZONE_AFTER_HOURS: {
        "event_types": ["person", "intrusion"],
        "after": "21:00",
        "require_zone": True,
    },
    RULE_LOITERING: {
        "min_seconds": 60,
        "event_types": ["person", "intrusion"],
    },
    RULE_UNKNOWN_FACE: {},
}


def as_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _local_minutes(dt: datetime) -> int:
    local = as_utc(dt).astimezone()
    return local.hour * 60 + local.minute


def _parse_hhmm(value: str) -> int:
    parts = (value or "21:00").strip().split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    return hour * 60 + minute


def _type_ok(event: Event, types: list | None) -> bool:
    if not types:
        return True
    meta = event.metadata_json or {}
    if event.event_type in types:
        return True
    return meta.get("object") in types


def _channel(value: str | None) -> str:
    if value in ("webhook", "email"):
        return value
    return "webhook"


def write_audit(db: Session, user, action: str, target: str, detail: str | None = None) -> AuditLog:
    row = AuditLog(
        actor_id=getattr(user, "id", None) if user is not None else None,
        actor_email=(getattr(user, "email", None) or "system") if user is not None else "system",
        action=action,
        target=target,
        detail=detail,
        ts=utcnow(),
    )
    db.add(row)
    return row


def record_alert(
    db: Session,
    *,
    event: Event | None,
    title: str,
    message: str,
    priority: str = "high",
    policy_id: int | None = None,
    channel: str = "webhook",
) -> Alert:
    """Persist an alert and a pending outbox row. Does not commit."""
    alert = Alert(
        event_id=event.id if event is not None else None,
        camera_id=event.camera_id if event is not None else None,
        policy_id=policy_id,
        title=title,
        message=message,
        priority=priority,
        is_active=True,
        acknowledged=False,
    )
    db.add(alert)
    db.flush()
    payload = {
        "alert_id": alert.id,
        "title": alert.title,
        "message": alert.message,
        "priority": alert.priority,
        "event_id": alert.event_id,
        "camera_id": alert.camera_id,
        "policy_id": alert.policy_id,
    }
    db.add(
        NotificationOutbox(
            alert_id=alert.id,
            channel=_channel(channel),
            payload=payload,
            status="pending",
        )
    )
    db.flush()
    return alert


def _loitering_span(db: Session, event: Event, min_seconds: int) -> float | None:
    if event.track_id is None:
        return None
    peers = (
        db.query(Event)
        .filter(Event.camera_id == event.camera_id, Event.track_id == event.track_id)
        .all()
    )
    if len(peers) < 2:
        return None
    times = [as_utc(p.timestamp) for p in peers]
    span = (max(times) - min(times)).total_seconds()
    if span < min_seconds:
        return None
    # Fire once, on the latest sighting of this track.
    if as_utc(event.timestamp) < max(times):
        return None
    return span


def policy_match_detail(db: Session, policy: AlertPolicy, event: Event) -> dict | None:
    """Return match context when the policy applies to this event."""
    if not policy.enabled:
        return None
    config = policy.config or {}
    rule = policy.rule_type

    if rule == RULE_ZONE_AFTER_HOURS:
        if config.get("require_zone", True) and not event.zone_id:
            return None
        if not _type_ok(event, config.get("event_types") or ["person", "intrusion"]):
            return None
        after = config.get("after") or "21:00"
        if _local_minutes(event.timestamp) < _parse_hhmm(str(after)):
            return None
        return {"after": after}

    if rule == RULE_LOITERING:
        if not _type_ok(event, config.get("event_types") or ["person", "intrusion"]):
            return None
        min_seconds = int(config.get("min_seconds") or 60)
        span = _loitering_span(db, event, min_seconds)
        if span is None:
            return None
        return {"span_seconds": span, "min_seconds": min_seconds}

    if rule == RULE_UNKNOWN_FACE:
        meta = event.metadata_json or {}
        category = str(meta.get("face_category") or "")
        label = (event.label or "").lower()
        if category == "unknown":
            return {"face_name": meta.get("face_name")}
        if event.event_type == "face" and "unknown" in label:
            return {"face_name": meta.get("face_name")}
        return None

    return None


def _alert_copy(policy: AlertPolicy, event: Event, detail: dict) -> tuple[str, str]:
    if policy.rule_type == RULE_LOITERING:
        span = int(detail.get("span_seconds") or 0)
        minimum = int(detail.get("min_seconds") or 0)
        return (
            policy.name,
            f"Track #{event.track_id} seen for {span}s (threshold {minimum}s). {event.label}",
        )
    if policy.rule_type == RULE_ZONE_AFTER_HOURS:
        after = detail.get("after") or "21:00"
        return (
            policy.name,
            f"{event.label} inside a zone after {after} (server local time).",
        )
    if policy.rule_type == RULE_UNKNOWN_FACE:
        return policy.name, event.label or "Unknown face"
    return policy.name, event.label


def evaluate_policies(db: Session, event: Event) -> list[Alert]:
    """Evaluate enabled policies against one event and create Alert rows."""
    created: list[Alert] = []
    policies = db.query(AlertPolicy).filter(AlertPolicy.enabled == True).all()  # noqa: E712
    for policy in policies:
        detail = policy_match_detail(db, policy, event)
        if detail is None:
            continue
        existing = (
            db.query(Alert)
            .filter(Alert.policy_id == policy.id, Alert.event_id == event.id)
            .first()
        )
        if existing:
            continue
        title, message = _alert_copy(policy, event, detail)
        created.append(
            record_alert(
                db,
                event=event,
                title=title,
                message=message,
                priority=policy.priority or "high",
                policy_id=policy.id,
                channel=policy.notify_channel or "webhook",
            )
        )
    return created


def evaluate_all_events(db: Session) -> int:
    count = 0
    events = db.query(Event).order_by(Event.timestamp.asc()).all()
    for event in events:
        count += len(evaluate_policies(db, event))
    return count


def _site_for_camera(cam: Camera, hq: Site, warehouse: Site) -> int:
    blob = f"{cam.name} {cam.location}".lower()
    if "warehouse" in blob or "loading" in blob:
        return warehouse.id
    return hq.id


def apply_sites(db: Session) -> tuple[Site, Site]:
    """Ensure HQ and Warehouse exist and unassigned cameras get a site."""
    hq = db.query(Site).filter(Site.code == "HQ").first()
    warehouse = db.query(Site).filter(Site.code == "WH").first()
    if hq is None:
        hq = Site(name="HQ", code="HQ", address="Headquarters")
        db.add(hq)
    if warehouse is None:
        warehouse = Site(name="Warehouse", code="WH", address="Warehouse campus")
        db.add(warehouse)
    db.flush()
    for cam in db.query(Camera).all():
        if cam.site_id is None:
            cam.site_id = _site_for_camera(cam, hq, warehouse)
    return hq, warehouse


def attach_default_site(db: Session, cam: Camera) -> None:
    if cam.site_id is not None:
        return
    hq = db.query(Site).filter(Site.code == "HQ").first()
    warehouse = db.query(Site).filter(Site.code == "WH").first()
    if hq is None:
        return
    if warehouse is None:
        cam.site_id = hq.id
        return
    cam.site_id = _site_for_camera(cam, hq, warehouse)


def default_policy_rows() -> list[AlertPolicy]:
    return [
        AlertPolicy(
            name="Person in a zone after 21:00",
            rule_type=RULE_ZONE_AFTER_HOURS,
            enabled=True,
            config=dict(DEFAULT_CONFIG[RULE_ZONE_AFTER_HOURS]),
            priority="high",
            notify_channel="email",
        ),
        AlertPolicy(
            name="Loitering over 60 seconds",
            rule_type=RULE_LOITERING,
            enabled=True,
            config=dict(DEFAULT_CONFIG[RULE_LOITERING]),
            priority="high",
            notify_channel="webhook",
        ),
    ]


def _backfill_outbox(db: Session) -> None:
    existing = {row[0] for row in db.query(NotificationOutbox.alert_id).all()}
    for alert in db.query(Alert).all():
        if alert.id in existing:
            continue
        db.add(
            NotificationOutbox(
                alert_id=alert.id,
                channel="webhook",
                payload={
                    "alert_id": alert.id,
                    "title": alert.title,
                    "message": alert.message,
                    "priority": alert.priority,
                    "event_id": alert.event_id,
                    "camera_id": alert.camera_id,
                    "policy_id": alert.policy_id,
                },
                status="pending",
            )
        )


def seed_default_policies(db: Session, actor=None) -> None:
    """Create the two demo policies once, then evaluate stored events."""
    if db.query(AlertPolicy).count() == 0:
        rows = default_policy_rows()
        db.add_all(rows)
        db.flush()
        for row in rows:
            write_audit(db, actor, "policy.create", f"policy:{row.id}", row.name)
        evaluate_all_events(db)
    elif db.query(Alert).filter(Alert.policy_id.isnot(None)).count() == 0:
        evaluate_all_events(db)
    _backfill_outbox(db)


def align_seeded_events(db: Session) -> None:
    """Give older demo databases the timestamps the seeded policies expect."""
    events = db.query(Event).order_by(Event.id).all()
    seeded = [
        event for event in events
        if isinstance(event.metadata_json, dict) and event.metadata_json.get("seeded")
    ]
    if any(isinstance(event.metadata_json, dict) and event.metadata_json.get("loiter_pair") for event in seeded):
        return
    if len(seeded) >= 2:
        tune_seed_events_for_policies(seeded, datetime.now(timezone.utc))
        for event in seeded:
            if event.id is None:
                db.add(event)
    has_unknown = any(
        isinstance(event.metadata_json, dict) and event.metadata_json.get("face_category") == "unknown"
        for event in events
    )
    if not has_unknown and seeded:
        db.add(
            Event(
                camera_id=seeded[0].camera_id,
                zone_id=None,
                event_type="face",
                label="Unknown face: Unknown Person #17",
                confidence=0.7,
                priority="high",
                timestamp=datetime.now(timezone.utc) - timedelta(minutes=8),
                metadata_json={
                    "face_name": "Unknown Person #17",
                    "face_category": "unknown",
                    "seeded": True,
                },
            )
        )
    db.flush()


def ensure_operations_data() -> None:
    """Idempotent backfill for databases that were seeded before this layer."""
    db = SessionLocal()
    try:
        from app.models import User

        apply_sites(db)
        if db.query(Alert).filter(Alert.policy_id.isnot(None)).count() == 0:
            align_seeded_events(db)
        admin = db.query(User).filter(User.role == "admin").order_by(User.id).first()
        seed_default_policies(db, admin)
        db.commit()
    finally:
        db.close()


def tune_seed_events_for_policies(events: list[Event], now: datetime) -> None:
    """Point a couple of seeded events at the demo policies.

    After-hours uses the server local clock so '21:00' means 9pm where the
    process runs. Loitering reuses one track id across two person timestamps.
    """
    if not events:
        return
    local_now = datetime.now().astimezone()
    evening = local_now.replace(hour=21, minute=40, second=0, microsecond=0)
    if evening > local_now:
        evening = evening - timedelta(days=1)
    events[0].timestamp = evening.astimezone(timezone.utc)

    if len(events) < 2:
        return
    anchor = now - timedelta(minutes=20)
    events[1].track_id = 77
    events[1].event_type = "person"
    events[1].label = events[1].label or "Person detected"
    events[1].timestamp = anchor
    meta = dict(events[1].metadata_json or {})
    meta["object"] = "person"
    meta["seeded"] = True
    events[1].metadata_json = meta

    events.append(
        Event(
            camera_id=events[1].camera_id,
            zone_id=None,
            event_type="person",
            label="Person detected",
            confidence=events[1].confidence or 0.9,
            priority="high",
            track_id=77,
            bbox=events[1].bbox,
            timestamp=anchor + timedelta(seconds=95),
            metadata_json={"object": "person", "seeded": True, "loiter_pair": True},
        )
    )


def mark_outbox_sent(db: Session) -> int:
    """Simulated delivery: flip pending rows to sent. No network calls."""
    now = utcnow()
    rows = db.query(NotificationOutbox).filter(NotificationOutbox.status == "pending").all()
    for row in rows:
        row.status = "sent"
        row.sent_at = now
    return len(rows)
