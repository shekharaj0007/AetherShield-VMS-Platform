import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db, SessionLocal
from app.models import User, Camera, Recording, Event
from app.schemas import RecordingOut
from app.core.security import require_permission, decode_token
from app.core.config import get_settings
from app.services.stream_manager import stream_manager

router = APIRouter(tags=["streaming"])
settings = get_settings()


def _auth_from_query(token: Optional[str]) -> User:
    """Allow token via query for <img src> / video elements."""
    if not token:
        raise HTTPException(401, "Missing token")
    payload = decode_token(token)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(payload["sub"])).first()
        if not user:
            raise HTTPException(401, "Invalid user")
        return user
    finally:
        db.close()


@router.get("/api/stream/{camera_id}/mjpeg")
async def mjpeg_stream(camera_id: int, token: str = Query(...)):
    _auth_from_query(token)
    stream = stream_manager.get(camera_id)
    if not stream:
        raise HTTPException(404, "Stream not running")

    async def generate():
        while True:
            jpeg = stream.get_jpeg(annotated=True)
            if jpeg:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                )
            await asyncio.sleep(1 / max(settings.DEFAULT_FPS, 1))

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/api/stream/{camera_id}/snapshot")
def snapshot(camera_id: int, token: str = Query(...)):
    _auth_from_query(token)
    stream = stream_manager.get(camera_id)
    if not stream:
        raise HTTPException(404, "Stream not running")
    jpeg = stream.get_jpeg(annotated=True)
    if not jpeg:
        raise HTTPException(503, "No frame available")
    return StreamingResponse(iter([jpeg]), media_type="image/jpeg")


@router.get("/api/recordings", response_model=list[RecordingOut])
def list_recordings(
    camera_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("recordings:read")),
):
    # Ingest any pending segment JSON sidecars
    _ingest_recording_metas(db)
    q = db.query(Recording)
    if camera_id:
        q = q.filter(Recording.camera_id == camera_id)
    return q.order_by(Recording.start_time.desc()).limit(200).all()


@router.get("/api/recordings/{recording_id}/video")
def play_recording(
    recording_id: int,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    _auth_from_query(token)
    rec = db.query(Recording).filter(Recording.id == recording_id).first()
    if not rec:
        raise HTTPException(404, "Recording not found")
    path = settings.BASE_DIR / rec.file_path
    if not path.exists():
        raise HTTPException(404, "Recording file missing")
    return FileResponse(path, media_type="video/mp4", filename=path.name)


@router.get("/api/recordings/by-event/{event_id}")
def recording_for_event(
    event_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("recordings:read")),
):
    """Find recording covering an event timestamp + replay window."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "Event not found")
    _ingest_recording_metas(db)
    recs = (
        db.query(Recording)
        .filter(Recording.camera_id == event.camera_id)
        .order_by(Recording.start_time.desc())
        .all()
    )
    chosen = None
    for r in recs:
        if r.start_time <= event.timestamp and (r.end_time is None or r.end_time >= event.timestamp):
            chosen = r
            break
    if not chosen and recs:
        chosen = recs[0]

    offset = 0.0
    if chosen:
        offset = max(0.0, (event.timestamp - chosen.start_time).total_seconds() - 10)

    return {
        "event_id": event_id,
        "recording": RecordingOut.model_validate(chosen) if chosen else None,
        "seek_seconds": offset,
        "replay_before": 10,
        "replay_after": 20,
        "event_timestamp": event.timestamp.isoformat(),
        "bbox": event.bbox,
    }


@router.get("/api/media/snapshot")
def get_snapshot_file(path: str, token: str = Query(...)):
    _auth_from_query(token)
    # prevent path traversal
    full = (settings.BASE_DIR / path).resolve()
    if not str(full).startswith(str(settings.BASE_DIR.resolve())):
        raise HTTPException(400, "Invalid path")
    if not full.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(full, media_type="image/jpeg")


def _ingest_recording_metas(db: Session):
    for meta_path in settings.RECORDINGS_DIR.rglob("*.json"):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            existing = db.query(Recording).filter(Recording.file_path == data["file_path"]).first()
            if existing:
                meta_path.unlink(missing_ok=True)
                continue
            rec = Recording(
                camera_id=data["camera_id"],
                file_path=data["file_path"],
                start_time=datetime.fromisoformat(data["start_time"]),
                end_time=datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None,
                duration_seconds=data.get("duration_seconds", 0),
                file_size_bytes=data.get("file_size_bytes", 0),
            )
            db.add(rec)
            db.commit()
            meta_path.unlink(missing_ok=True)
        except Exception:
            continue
