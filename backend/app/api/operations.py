"""Sites, alert policies, alerts, audit log, and notification outbox."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_permission
from app.db.session import get_db
from app.models import Alert, AlertPolicy, AuditLog, Camera, NotificationOutbox, Site, User
from app.schemas import (
    AlertOut,
    AuditOut,
    OutboxOut,
    PolicyCreate,
    PolicyOut,
    PolicyUpdate,
    SiteCreate,
    SiteOut,
    SiteUpdate,
)
from app.services.operations import (
    RULE_TYPES,
    DEFAULT_CONFIG,
    evaluate_all_events,
    mark_outbox_sent,
    write_audit,
    _channel,
)

router = APIRouter(tags=["operations"])


def _site_out(site: Site, db: Session) -> SiteOut:
    count = db.query(Camera).filter(Camera.site_id == site.id).count()
    data = SiteOut.model_validate(site)
    data.camera_count = count
    return data


@router.get("/api/sites", response_model=list[SiteOut])
def list_sites(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sites:read")),
):
    return [_site_out(s, db) for s in db.query(Site).order_by(Site.id).all()]


@router.post("/api/sites", response_model=SiteOut)
def create_site(
    body: SiteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("sites:write")),
):
    code = body.code.strip().upper()
    if not code:
        raise HTTPException(400, "code is required")
    if db.query(Site).filter(Site.code == code).first():
        raise HTTPException(400, "Site code already exists")
    site = Site(name=body.name.strip(), code=code, address=body.address or "")
    db.add(site)
    db.flush()
    write_audit(db, user, "site.create", f"site:{site.id}", site.name)
    db.commit()
    db.refresh(site)
    return _site_out(site, db)


@router.patch("/api/sites/{site_id}", response_model=SiteOut)
def update_site(
    site_id: int,
    body: SiteUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("sites:write")),
):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(404, "Site not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(site, key, value)
    write_audit(db, user, "site.update", f"site:{site.id}", site.name)
    db.commit()
    db.refresh(site)
    return _site_out(site, db)


def _policy_out(row: AlertPolicy) -> PolicyOut:
    data = PolicyOut.model_validate(row)
    data.config = row.config or {}
    return data


def _normalize_policy(body_rule: str, config: dict | None, channel: str) -> tuple[str, dict, str]:
    rule = (body_rule or "").strip()
    if rule not in RULE_TYPES:
        raise HTTPException(400, "rule_type must be zone_after_hours, loitering, or unknown_face")
    merged = dict(DEFAULT_CONFIG.get(rule) or {})
    if config:
        merged.update(config)
    return rule, merged, _channel(channel)


@router.get("/api/policies", response_model=list[PolicyOut])
def list_policies(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("policies:read")),
):
    rows = db.query(AlertPolicy).order_by(AlertPolicy.id).all()
    return [_policy_out(r) for r in rows]


@router.post("/api/policies", response_model=PolicyOut)
def create_policy(
    body: PolicyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("policies:write")),
):
    rule, config, channel = _normalize_policy(body.rule_type, body.config, body.notify_channel)
    row = AlertPolicy(
        name=body.name.strip(),
        rule_type=rule,
        enabled=body.enabled,
        config=config,
        priority=body.priority or "high",
        notify_channel=channel,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.flush()
    write_audit(db, user, "policy.create", f"policy:{row.id}", row.name)
    if row.enabled:
        evaluate_all_events(db)
    db.commit()
    db.refresh(row)
    return _policy_out(row)


@router.patch("/api/policies/{policy_id}", response_model=PolicyOut)
def update_policy(
    policy_id: int,
    body: PolicyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("policies:write")),
):
    row = db.query(AlertPolicy).filter(AlertPolicy.id == policy_id).first()
    if not row:
        raise HTTPException(404, "Policy not found")
    changes = body.model_dump(exclude_unset=True)
    if "rule_type" in changes or "config" in changes or "notify_channel" in changes:
        rule, config, channel = _normalize_policy(
            changes.get("rule_type") or row.rule_type,
            changes.get("config") if "config" in changes else (row.config or {}),
            changes.get("notify_channel") or row.notify_channel,
        )
        row.rule_type = rule
        row.config = config
        row.notify_channel = channel
    if "name" in changes and changes["name"]:
        row.name = changes["name"].strip()
    if "enabled" in changes:
        row.enabled = bool(changes["enabled"])
    if "priority" in changes and changes["priority"]:
        row.priority = changes["priority"]
    row.updated_at = datetime.now(timezone.utc)
    write_audit(db, user, "policy.update", f"policy:{row.id}", row.name)
    if row.enabled:
        evaluate_all_events(db)
    db.commit()
    db.refresh(row)
    return _policy_out(row)


@router.delete("/api/policies/{policy_id}")
def delete_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("policies:write")),
):
    row = db.query(AlertPolicy).filter(AlertPolicy.id == policy_id).first()
    if not row:
        raise HTTPException(404, "Policy not found")
    write_audit(db, user, "policy.delete", f"policy:{row.id}", row.name)
    db.query(Alert).filter(Alert.policy_id == row.id).update({Alert.policy_id: None})
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/api/alerts", response_model=list[AlertOut])
def list_alerts(
    active_only: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("alerts:read")),
):
    q = db.query(Alert)
    if active_only:
        q = q.filter(Alert.is_active == True)  # noqa: E712
    return q.order_by(Alert.created_at.desc()).limit(100).all()


@router.post("/api/alerts/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("alerts:ack")),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.is_active = False
    alert.acknowledged = True
    alert.acknowledged_by = user.id
    alert.acknowledged_at = datetime.now(timezone.utc)
    if alert.event_id:
        from app.models import Event

        event = db.query(Event).filter(Event.id == alert.event_id).first()
        if event:
            event.acknowledged = True
    write_audit(db, user, "alert.acknowledge", f"alert:{alert.id}", alert.title)
    db.commit()
    db.refresh(alert)
    return alert


@router.get("/api/audit", response_model=list[AuditOut])
def list_audit(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("audit:read")),
):
    rows = db.query(AuditLog).order_by(AuditLog.ts.desc()).limit(100).all()
    return [
        AuditOut(
            id=row.id,
            actor=row.actor_email,
            action=row.action,
            target=row.target,
            detail=row.detail,
            ts=row.ts,
        )
        for row in rows
    ]


@router.get("/api/outbox", response_model=list[OutboxOut])
def list_outbox(
    status: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("outbox:read")),
):
    q = db.query(NotificationOutbox)
    if status:
        q = q.filter(NotificationOutbox.status == status)
    return q.order_by(NotificationOutbox.created_at.desc()).limit(100).all()


@router.post("/api/outbox/deliver")
def deliver_outbox(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("outbox:deliver")),
):
    """Mark every pending outbox row sent. Simulated only — no outbound HTTP."""
    delivered = mark_outbox_sent(db)
    db.commit()
    return {"ok": True, "delivered": delivered, "simulated": True}
