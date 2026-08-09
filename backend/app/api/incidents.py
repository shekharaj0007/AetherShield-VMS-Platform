from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User, Incident, Event, Camera
from app.schemas import IncidentOut, IncidentUpdate, EventOut
from app.core.security import require_permission

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


def _out(inc: Incident, db: Session) -> IncidentOut:
    data = IncidentOut.model_validate(inc)
    if inc.event:
        cam = db.query(Camera).filter(Camera.id == inc.event.camera_id).first()
        eo = EventOut.model_validate(inc.event)
        eo.camera_name = cam.name if cam else None
        data.event = eo
    return data


@router.get("", response_model=list[IncidentOut])
def list_incidents(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("incidents:manage")),
):
    q = db.query(Incident)
    if status:
        q = q.filter(Incident.status == status)
    return [_out(i, db) for i in q.order_by(Incident.created_at.desc()).limit(100).all()]


@router.patch("/{incident_id}", response_model=IncidentOut)
def update_incident(
    incident_id: int,
    body: IncidentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("incidents:manage")),
):
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(404, "Incident not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(inc, k, v)
    if body.assigned_to is None and "assigned_to" not in body.model_dump(exclude_unset=True):
        pass
    elif body.assigned_to is None:
        pass
    inc.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(inc)
    return _out(inc, db)


@router.post("/from-event/{event_id}", response_model=IncidentOut)
def create_from_event(
    event_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("incidents:manage")),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "Event not found")
    existing = db.query(Incident).filter(Incident.event_id == event_id).first()
    if existing:
        return _out(existing, db)
    inc = Incident(event_id=event_id, status="open", notes="")
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return _out(inc, db)
