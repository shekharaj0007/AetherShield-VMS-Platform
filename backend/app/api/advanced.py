"""Advanced AI APIs — faces, plates, heatmap, webcam probe, clip export."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import cv2
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import require_permission, decode_token
from app.db.session import get_db, SessionLocal
from app.models import User, Event, Camera, Recording
from app.ai.faces import list_faces, enroll_face, delete_face, seed_demo_faces
from app.ai import heatmap as heatmap_svc
from app.services.stream_manager import stream_manager

router = APIRouter(prefix="/api/advanced", tags=["advanced"])
settings = get_settings()


class FaceOut(BaseModel):
    name: str
    category: str
    path: str


class WebcamTestResult(BaseModel):
    ok: bool
    index: int
    message: str
    width: Optional[int] = None
    height: Optional[int] = None


@router.get("/faces", response_model=list[FaceOut])
def get_faces(_: User = Depends(require_permission("cameras:read"))):
    seed_demo_faces()
    return [
        FaceOut(name=f["name"], category=f["category"], path=f.get("path", ""))
        for f in list_faces()
    ]


@router.post("/faces", response_model=FaceOut)
async def add_face(
    name: str = Form(...),
    category: str = Form("known"),
    file: UploadFile = File(...),
    _: User = Depends(require_permission("cameras:write")),
):
    data = await file.read()
    try:
        entry = enroll_face(name, category, data)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return FaceOut(**entry)


@router.delete("/faces/{name}")
def remove_face(name: str, _: User = Depends(require_permission("cameras:write"))):
    if not delete_face(name):
        raise HTTPException(404, "Face not found")
    return {"ok": True}


@router.get("/heatmap/{camera_id}")
def camera_heatmap(
    camera_id: int,
    token: str = Query(...),
):
    payload = decode_token(token)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(payload["sub"])).first()
        if not user:
            raise HTTPException(401, "Invalid user")
    finally:
        db.close()
    png = heatmap_svc.render_heatmap_png(camera_id)
    if not png:
        raise HTTPException(404, "No heatmap data yet")
    return Response(content=png, media_type="image/png")


@router.post("/heatmap/{camera_id}/reset")
def reset_heatmap(camera_id: int, _: User = Depends(require_permission("cameras:write"))):
    heatmap_svc.reset(camera_id)
    return {"ok": True}


@router.get("/webcam/probe", response_model=list[WebcamTestResult])
def probe_webcams(_: User = Depends(require_permission("cameras:read"))):
    """Try camera indices 0–3 and report which open."""
    results = []
    for idx in range(4):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            ok, _ = cap.read()
            cap.release()
            results.append(WebcamTestResult(
                ok=bool(ok),
                index=idx,
                message="Available" if ok else "Opened but no frame",
                width=w,
                height=h,
            ))
        else:
            results.append(WebcamTestResult(ok=False, index=idx, message="Not available"))
    return results


@router.post("/webcam/connect")
def connect_webcam(
    index: int = 0,
    name: str = "Webcam",
    location: str = "Local",
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("cameras:write")),
):
    """Create (or reuse) a webcam camera and start streaming."""
    existing = (
        db.query(Camera)
        .filter(Camera.source_type == "webcam", Camera.source_uri == str(index))
        .first()
    )
    if existing:
        cam = existing
        cam.enabled = True
        cam.name = name or cam.name
        cam.is_demo = False
    else:
        cam = Camera(
            name=name,
            location=location,
            source_type="webcam",
            source_uri=str(index),
            status="online",
            resolution="1280x720",
            fps=15,
            ai_enabled=True,
            map_x=0.15,
            map_y=0.8,
            is_demo=False,
            enabled=True,
        )
        db.add(cam)
        db.commit()
        db.refresh(cam)

    stream_manager.start_camera(cam.id, "webcam", str(index), True, [])
    cam.status = "online"
    cam.enabled = True
    db.commit()
    return {
        "ok": True,
        "camera_id": cam.id,
        "name": cam.name,
        "message": f"Webcam index {index} connected as camera #{cam.id}. Open Live View.",
    }


@router.get("/plates/search")
def search_plates(
    q: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("events:read")),
):
    qn = q.upper().replace(" ", "")
    events = (
        db.query(Event)
        .filter(Event.event_type == "plate")
        .order_by(Event.timestamp.desc())
        .limit(200)
        .all()
    )
    hits = []
    for e in events:
        plate = (e.metadata_json or {}).get("plate", "")
        if qn in plate.upper().replace(" ", "") or qn in e.label.upper().replace(" ", ""):
            hits.append({
                "id": e.id,
                "camera_id": e.camera_id,
                "label": e.label,
                "plate": plate,
                "timestamp": e.timestamp.isoformat(),
                "confidence": e.confidence,
            })
    return hits


@router.get("/clips/export/{event_id}")
def export_clip(
    event_id: int,
    before: int = 10,
    after: int = 20,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """Export MP4 clip around an event (before/after seconds)."""
    payload = decode_token(token)
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(401, "Invalid user")

    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "Event not found")

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
    if not chosen:
        # fallback: use live camera source file
        cam = db.query(Camera).filter(Camera.id == event.camera_id).first()
        if not cam:
            raise HTTPException(404, "No recording")
        src = settings.BASE_DIR / cam.source_uri
    else:
        src = settings.BASE_DIR / chosen.file_path

    if not src.exists():
        raise HTTPException(404, "Source video missing")

    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        raise HTTPException(500, "Cannot open source video")
    fps = cap.get(cv2.CAP_PROP_FPS) or 15
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 360)

    if chosen:
        offset = max(0.0, (event.timestamp - chosen.start_time).total_seconds() - before)
    else:
        offset = 0
    start_frame = int(offset * fps)
    end_frame = int(min(total, start_frame + (before + after) * fps)) if total else start_frame + int((before + after) * fps)

    out_dir = settings.STORAGE_DIR / "clips"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"event_{event_id}_{int(datetime.now(timezone.utc).timestamp())}.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, fps, (w, h))
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    idx = start_frame
    while idx <= end_frame:
        ok, frame = cap.read()
        if not ok:
            break
        writer.write(frame)
        idx += 1
    writer.release()
    cap.release()

    return FileResponse(
        out_path,
        media_type="video/mp4",
        filename=f"clip_event_{event_id}.mp4",
    )
