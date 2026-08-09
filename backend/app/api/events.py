from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User, Event, Camera, Alert, Incident
from app.schemas import EventOut, EventSearchQuery, ChatRequest, ChatResponse, SummaryResponse
from app.core.security import require_permission
from app.services.ai_search import search_events, build_summary, chat_with_events

router = APIRouter(prefix="/api/events", tags=["events"])


def _to_out(e: Event, db: Session) -> EventOut:
    cam = db.query(Camera).filter(Camera.id == e.camera_id).first()
    data = EventOut.model_validate(e)
    data.camera_name = cam.name if cam else None
    return data


@router.get("", response_model=list[EventOut])
def list_events(
    camera_id: Optional[int] = None,
    event_type: Optional[str] = None,
    priority: Optional[str] = None,
    hours: Optional[int] = 24,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("events:read")),
):
    q = db.query(Event)
    if camera_id:
        q = q.filter(Event.camera_id == camera_id)
    if event_type:
        q = q.filter(Event.event_type == event_type)
    if priority:
        q = q.filter(Event.priority == priority)
    if hours:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        q = q.filter(Event.timestamp >= since)
    events = q.order_by(Event.timestamp.desc()).limit(limit).all()
    return [_to_out(e, db) for e in events]


@router.get("/timeline/{camera_id}", response_model=list[EventOut])
def camera_timeline(
    camera_id: int,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("events:read")),
):
    q = db.query(Event).filter(Event.camera_id == camera_id)
    if start:
        q = q.filter(Event.timestamp >= start)
    if end:
        q = q.filter(Event.timestamp <= end)
    else:
        q = q.filter(Event.timestamp >= datetime.now(timezone.utc) - timedelta(hours=24))
    events = q.order_by(Event.timestamp.asc()).all()
    return [_to_out(e, db) for e in events]


@router.post("/search", response_model=list[EventOut])
def nl_search(
    body: EventSearchQuery,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("events:read")),
):
    events = search_events(db, body.query, body.camera_id, body.start, body.end, body.limit)
    return [_to_out(e, db) for e in events]


@router.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("events:read")),
):
    result = chat_with_events(db, body.message, body.camera_id)
    return ChatResponse(
        reply=result["reply"],
        events=[_to_out(e, db) for e in result.get("events", [])],
        sources=result.get("sources", []),
    )


@router.get("/ai/summary", response_model=SummaryResponse)
def summary(
    hours: int = 24,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("analytics:read")),
):
    data = build_summary(db, hours)
    return SummaryResponse(**data)


@router.get("/{event_id}", response_model=EventOut)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("events:read")),
):
    e = db.query(Event).filter(Event.id == event_id).first()
    if not e:
        raise HTTPException(404, "Event not found")
    return _to_out(e, db)


@router.post("/{event_id}/acknowledge")
def acknowledge(
    event_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("events:write")),
):
    e = db.query(Event).filter(Event.id == event_id).first()
    if not e:
        raise HTTPException(404, "Event not found")
    e.acknowledged = True
    alert = db.query(Alert).filter(Alert.event_id == event_id, Alert.is_active == True).first()  # noqa: E712
    if alert:
        alert.is_active = False
    db.commit()
    return {"ok": True}
