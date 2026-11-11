"""Camera heartbeats, operator shifts, and watchlist matching.

Watchlist hits go through record_alert so they land in the same alert and
outbox tables as policy alerts. Seeded demo events have no plate text; the
demo watchlist matches metadata.object == "person" and the event label.
Plate entries match metadata.plate when a live detection stores one.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    Camera,
    Event,
    Shift,
    ShiftNote,
    Site,
    User,
    WatchlistEntry,
    WatchlistHit,
    utcnow,
)
from app.services.operations import as_utc, record_alert, write_audit

HEARTBEAT_WINDOW = timedelta(minutes=15)
SEEDED_PERSON_LABEL = "Person detected"
SEEDED_PERSON_NOTE = (
    "Seeded events have no plate text. This entry matches metadata.object "
    "'person' and the event label 'Person detected'."
)


def heartbeat_status(cam: Camera, now: datetime | None = None) -> str:
    """Online only when the camera is enabled and heartbeated within 15 minutes."""
    if not getattr(cam, "enabled", True):
        return "offline"
    seen = getattr(cam, "last_seen_at", None)
    if seen is None:
        return "offline"
    now = now or datetime.now(timezone.utc)
    if as_utc(now) - as_utc(seen) >= HEARTBEAT_WINDOW:
        return "offline"
    if cam.status == "error":
        return "error"
    return "online"


def presented_status(cam: Camera, stream_status: str | None = None, now: datetime | None = None) -> str:
    """Heartbeat wins. A live stream error is shown only while the heartbeat is fresh."""
    status = heartbeat_status(cam, now)
    if stream_status == "error" and status == "online":
        return "error"
    return status


def touch_heartbeat(cam: Camera, when: datetime | None = None) -> str:
    cam.last_seen_at = when or utcnow()
    cam.status = "online" if getattr(cam, "enabled", True) else "offline"
    return cam.status


def sync_camera_health(db: Session, now: datetime | None = None) -> tuple[int, int]:
    """Persist status from last_seen_at. Returns (online, offline)."""
    now = now or datetime.now(timezone.utc)
    online = 0
    offline = 0
    for cam in db.query(Camera).all():
        status = heartbeat_status(cam, now)
        cam.status = status
        if status == "online":
            online += 1
        else:
            offline += 1
    return online, offline


def seed_camera_heartbeats(db: Session, now: datetime | None = None) -> None:
    """First time only: every camera but the last is fresh; the last is offline."""
    cameras = db.query(Camera).order_by(Camera.id).all()
    if not cameras:
        return
    if any(cam.last_seen_at is not None for cam in cameras):
        sync_camera_health(db, now)
        return
    now = now or datetime.now(timezone.utc)
    stale = now - timedelta(minutes=20)
    for cam in cameras[:-1]:
        cam.last_seen_at = now
        cam.status = "online"
    cameras[-1].last_seen_at = stale
    cameras[-1].status = "offline"


def seed_current_shift(db: Session, now: datetime | None = None) -> Shift | None:
    now = as_utc(now or datetime.now(timezone.utc))
    for row in db.query(Shift).order_by(Shift.id).all():
        if as_utc(row.starts_at) <= now <= as_utc(row.ends_at):
            return row
    operator = db.query(User).filter(User.email == "operator@aethershield.io").first()
    if operator is None:
        operator = db.query(User).filter(User.role == "operator").order_by(User.id).first()
    site = db.query(Site).filter(Site.code == "HQ").first()
    if site is None:
        site = db.query(Site).order_by(Site.id).first()
    if operator is None or site is None:
        return None
    shift = Shift(
        site_id=site.id,
        operator_id=operator.id,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=7),
    )
    db.add(shift)
    db.flush()
    return shift


def _norm_plate(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch.isalnum())


def event_matches_entry(event: Event, entry: WatchlistEntry) -> bool:
    """Match plate text or person class + label using fields events already store."""
    if not entry.enabled:
        return False
    meta = event.metadata_json if isinstance(event.metadata_json, dict) else {}
    kind = (entry.kind or "").strip().lower()
    wanted = (entry.value or "").strip()
    if not wanted:
        return False
    if kind == "plate":
        plate = meta.get("plate")
        if plate is None or str(plate).strip() == "":
            return False
        return _norm_plate(str(plate)) == _norm_plate(wanted)
    if kind == "person":
        if str(meta.get("object") or "").strip().lower() != "person":
            return False
        return (event.label or "").strip().lower() == wanted.lower()
    return False


def _hit_exists(db: Session, entry_id: int, event_id: int) -> bool:
    return (
        db.query(WatchlistHit)
        .filter(WatchlistHit.entry_id == entry_id, WatchlistHit.event_id == event_id)
        .first()
        is not None
    )


def record_watch_hit(db: Session, entry: WatchlistEntry, event: Event):
    """Create an alert through the shared path and a match row. Does not commit."""
    if entry.id is None or event.id is None:
        db.flush()
    if _hit_exists(db, entry.id, event.id):
        return None
    alert = record_alert(
        db,
        event=event,
        title=f"Watchlist: {entry.value}",
        message=(
            f"{entry.kind} watch '{entry.value}' matched event '{event.label}'."
        ),
        priority="high",
        channel="webhook",
    )
    db.add(WatchlistHit(entry_id=entry.id, event_id=event.id, alert_id=alert.id))
    db.flush()
    return alert


def evaluate_watchlist(db: Session, event: Event) -> list:
    created = []
    entries = db.query(WatchlistEntry).filter(WatchlistEntry.enabled == True).all()  # noqa: E712
    for entry in entries:
        if not event_matches_entry(event, entry):
            continue
        alert = record_watch_hit(db, entry, event)
        if alert is not None:
            created.append(alert)
    return created


def evaluate_all_watchlist(db: Session) -> int:
    count = 0
    for event in db.query(Event).order_by(Event.id).all():
        count += len(evaluate_watchlist(db, event))
    return count


def seed_watchlist(db: Session) -> WatchlistEntry | None:
    """One person entry that matches seeded events. Plate matching stays available."""
    row = (
        db.query(WatchlistEntry)
        .filter(WatchlistEntry.kind == "person", WatchlistEntry.value == SEEDED_PERSON_LABEL)
        .first()
    )
    if row is None:
        row = WatchlistEntry(
            kind="person",
            value=SEEDED_PERSON_LABEL,
            enabled=True,
            note=SEEDED_PERSON_NOTE,
        )
        db.add(row)
        db.flush()
    evaluate_all_watchlist(db)
    return row


def ensure_floor_data() -> None:
    """Idempotent heartbeats, one current shift, and the demo watchlist."""
    db = SessionLocal()
    try:
        seed_camera_heartbeats(db)
        seed_current_shift(db)
        seed_watchlist(db)
        db.commit()
    finally:
        db.close()


def add_shift_note(db: Session, shift: Shift, user: User, body: str) -> ShiftNote:
    note = ShiftNote(shift_id=shift.id, author_id=user.id, body=body.strip())
    db.add(note)
    write_audit(db, user, "shift.note", f"shift:{shift.id}", body.strip()[:240])
    db.flush()
    return note
