from datetime import datetime, timedelta, timezone
from pathlib import Path

import psutil
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.models import User, Camera, Event, Alert
from app.schemas import DashboardStats, EventOut, CameraOut, AlertOut
from app.core.security import require_permission
from app.core.config import get_settings
from app.services.stream_manager import stream_manager
from app.services.ai_search import build_summary

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
settings = get_settings()


@router.get("", response_model=DashboardStats)
def dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("analytics:read")),
):
    cameras = db.query(Camera).all()
    # Refresh live status from streams
    for cam in cameras:
        stream = stream_manager.get(cam.id)
        if stream:
            cam.status = stream.stats.status if stream.stats.status != "error" else "error"
            cam.fps = stream.stats.fps or cam.fps

    online = sum(1 for c in cameras if c.status in ("online", "recording"))
    offline = len(cameras) - online

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_events = db.query(Event).filter(Event.timestamp >= today_start).all()
    active_alerts = db.query(Alert).filter(Alert.is_active == True).all()  # noqa: E712

    # Storage
    used = 0
    for p in settings.STORAGE_DIR.rglob("*"):
        if p.is_file():
            used += p.stat().st_size
    used_gb = used / (1024 ** 3)
    total_gb = 50.0  # demo capacity
    # Predict days remaining based on last 24h growth approx
    day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_recs_size = used * 0.05  # rough for demo
    daily_gb = max(recent_recs_size / (1024 ** 3), 0.05)
    days_remaining = round((total_gb - used_gb) / daily_gb, 1) if daily_gb else None

    by_type: dict[str, int] = {}
    for e in today_events:
        by_type[e.event_type] = by_type.get(e.event_type, 0) + 1

    # Weekly graph
    weekly = []
    for i in range(6, -1, -1):
        day = today_start - timedelta(days=i)
        nxt = day + timedelta(days=1)
        count = db.query(func.count(Event.id)).filter(Event.timestamp >= day, Event.timestamp < nxt).scalar() or 0
        weekly.append({"date": day.strftime("%a"), "count": count})

    recent = (
        db.query(Event).order_by(Event.timestamp.desc()).limit(12).all()
    )
    recent_out = []
    for e in recent:
        cam = next((c for c in cameras if c.id == e.camera_id), None)
        eo = EventOut.model_validate(e)
        eo.camera_name = cam.name if cam else None
        recent_out.append(eo)

    summary = build_summary(db, 24)

    return DashboardStats(
        total_cameras=len(cameras),
        online_cameras=online,
        offline_cameras=offline,
        today_detections=len(today_events),
        active_alerts=len(active_alerts),
        storage_used_gb=round(used_gb, 3),
        storage_total_gb=total_gb,
        storage_days_remaining=days_remaining,
        cpu_percent=psutil.cpu_percent(interval=0.1),
        memory_percent=psutil.virtual_memory().percent,
        detections_by_type=by_type,
        weekly_detections=weekly,
        recent_events=recent_out,
        camera_health=[CameraOut.model_validate(c) for c in cameras],
        active_alerts_list=[AlertOut.model_validate(a).model_dump() for a in active_alerts],
        insights=summary["stats"],
    )


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(
    active_only: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("events:read")),
):
    q = db.query(Alert)
    if active_only:
        q = q.filter(Alert.is_active == True)  # noqa: E712
    return q.order_by(Alert.created_at.desc()).limit(50).all()
