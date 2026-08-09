from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User, Camera, DetectionZone
from app.schemas import CameraCreate, CameraUpdate, CameraOut, DemoToggle, RemoteCameraConnect
from app.core.security import require_permission
from app.services.stream_manager import stream_manager

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


def _zones_payload(db: Session, camera_id: int) -> list[dict]:
    zones = db.query(DetectionZone).filter(DetectionZone.camera_id == camera_id).all()
    return [
        {
            "id": z.id,
            "name": z.name,
            "shape": z.shape,
            "geometry": z.geometry,
            "sensitivity": z.sensitivity,
            "enabled": z.enabled,
            "trigger_classes": z.trigger_classes or [],
            "color": z.color,
        }
        for z in zones
    ]


def _start(db: Session, cam: Camera):
    stream_manager.start_camera(
        cam.id, cam.source_type, cam.source_uri, cam.ai_enabled, _zones_payload(db, cam.id)
    )
    cam.status = "online"


def _stop(cam: Camera):
    stream_manager.stop_camera(cam.id)
    cam.status = "offline"


@router.get("", response_model=list[CameraOut])
def list_cameras(
    include_disabled: bool = Query(False),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("cameras:read")),
):
    q = db.query(Camera).order_by(Camera.id)
    cams = q.all()
    if not include_disabled:
        cams = [c for c in cams if getattr(c, "enabled", True)]
    return cams


@router.get("/demo/status")
def demo_status(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("cameras:read")),
):
    demos = db.query(Camera).filter(Camera.is_demo == True).all()  # noqa: E712
    enabled = any(getattr(c, "enabled", True) for c in demos) if demos else False
    return {
        "demo_count": len(demos),
        "enabled": enabled,
        "cameras": [CameraOut.model_validate(c) for c in demos],
    }


@router.post("/demo/toggle")
def toggle_demo_cameras(
    body: DemoToggle,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("cameras:write")),
):
    """Turn all demo/sample cameras on or off (without deleting them)."""
    demos = db.query(Camera).filter(Camera.is_demo == True).all()  # noqa: E712
    for cam in demos:
        cam.enabled = body.enabled
        if body.enabled:
            _start(db, cam)
        else:
            _stop(cam)
    db.commit()
    return {
        "ok": True,
        "enabled": body.enabled,
        "affected": len(demos),
        "message": (
            f"Demo cameras turned {'ON' if body.enabled else 'OFF'} ({len(demos)} cameras)."
        ),
    }


@router.post("/connect-remote", response_model=CameraOut)
def connect_remote_camera(
    body: RemoteCameraConnect,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("cameras:write")),
):
    """Connect webcam / RTSP / HTTP stream from this PC or another device."""
    st = body.source_type.lower().strip()
    if st not in ("webcam", "rtsp", "http", "file"):
        raise HTTPException(400, "source_type must be webcam, rtsp, or http")
    uri = body.source_uri.strip()
    if not uri:
        raise HTTPException(400, "source_uri is required")

    # Reuse existing same source
    existing = (
        db.query(Camera)
        .filter(Camera.source_type == st, Camera.source_uri == uri)
        .first()
    )
    if existing:
        existing.enabled = True
        existing.name = body.name or existing.name
        existing.location = body.location or existing.location
        existing.ai_enabled = body.ai_enabled
        _start(db, existing)
        db.commit()
        db.refresh(existing)
        return existing

    cam = Camera(
        name=body.name,
        location=body.location,
        source_type=st,
        source_uri=uri,
        status="online",
        resolution="1280x720",
        fps=15,
        ai_enabled=body.ai_enabled,
        is_demo=False,
        enabled=True,
        map_x=0.2,
        map_y=0.75,
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)
    _start(db, cam)
    db.commit()
    db.refresh(cam)
    return cam


@router.post("/{camera_id}/disconnect")
def disconnect_camera(
    camera_id: int,
    remove: bool = Query(True, description="Delete camera after stopping (live cams)"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("cameras:write")),
):
    """Disconnect a live camera. Demo cams are only disabled, never deleted here."""
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")

    _stop(cam)

    if cam.is_demo:
        cam.enabled = False
        db.commit()
        return {
            "ok": True,
            "action": "disabled_demo",
            "message": f"Demo camera '{cam.name}' disabled (not deleted).",
        }

    if remove:
        db.delete(cam)
        db.commit()
        return {"ok": True, "action": "removed", "message": f"Disconnected and removed '{cam.name}'."}

    cam.enabled = False
    db.commit()
    return {"ok": True, "action": "stopped", "message": f"Stopped '{cam.name}'."}


@router.post("/disconnect-all-live")
def disconnect_all_live(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("cameras:write")),
):
    """Stop and remove every non-demo (live) camera."""
    lives = db.query(Camera).filter(Camera.is_demo == False).all()  # noqa: E712
    names = []
    for cam in lives:
        _stop(cam)
        names.append(cam.name)
        db.delete(cam)
    db.commit()
    return {
        "ok": True,
        "removed": len(names),
        "names": names,
        "message": f"Disconnected {len(names)} live camera(s).",
    }


@router.get("/{camera_id}", response_model=CameraOut)
def get_camera(camera_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("cameras:read"))):
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")
    return cam


@router.post("", response_model=CameraOut)
def create_camera(
    body: CameraCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("cameras:write")),
):
    data = body.model_dump()
    data.setdefault("is_demo", False)
    data.setdefault("enabled", True)
    cam = Camera(**data)
    db.add(cam)
    db.commit()
    db.refresh(cam)
    if cam.enabled:
        _start(db, cam)
        db.commit()
    return cam


@router.patch("/{camera_id}", response_model=CameraOut)
def update_camera(
    camera_id: int,
    body: CameraUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("cameras:write")),
):
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(cam, k, v)
    db.commit()
    db.refresh(cam)
    if cam.enabled:
        _start(db, cam)
    else:
        _stop(cam)
    db.commit()
    return cam


@router.delete("/{camera_id}")
def delete_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("cameras:delete")),
):
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")
    stream_manager.stop_camera(camera_id)
    db.delete(cam)
    db.commit()
    return {"ok": True}


@router.post("/{camera_id}/start")
def start_stream(
    camera_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("cameras:write")),
):
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")
    cam.enabled = True
    _start(db, cam)
    db.commit()
    return {"ok": True, "status": "online"}


@router.post("/{camera_id}/stop")
def stop_stream(
    camera_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("cameras:write")),
):
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")
    _stop(cam)
    db.commit()
    return {"ok": True, "status": "offline"}


@router.get("/{camera_id}/health")
def camera_health(
    camera_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("cameras:read")),
):
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")
    stream = stream_manager.get(camera_id)
    stats = stream.stats if stream else None
    return {
        "camera": CameraOut.model_validate(cam),
        "live_fps": stats.fps if stats else 0,
        "frame_count": stats.frame_count if stats else 0,
        "stream_status": stats.status if stats else "offline",
        "last_detections": stats.last_detections if stats else [],
        "error": stats.last_error if stats else None,
    }
