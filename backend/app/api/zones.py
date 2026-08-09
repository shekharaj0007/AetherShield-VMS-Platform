from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User, Camera, DetectionZone
from app.schemas import ZoneCreate, ZoneUpdate, ZoneOut
from app.core.security import require_permission
from app.services.stream_manager import stream_manager

router = APIRouter(prefix="/api/cameras/{camera_id}/zones", tags=["zones"])


def _sync_zones(db: Session, camera_id: int):
    zones = db.query(DetectionZone).filter(DetectionZone.camera_id == camera_id).all()
    payload = [
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
    stream_manager.update_zones(camera_id, payload)


@router.get("", response_model=list[ZoneOut])
def list_zones(
    camera_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("zones:read")),
):
    return db.query(DetectionZone).filter(DetectionZone.camera_id == camera_id).all()


@router.post("", response_model=ZoneOut)
def create_zone(
    camera_id: int,
    body: ZoneCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("zones:write")),
):
    if not db.query(Camera).filter(Camera.id == camera_id).first():
        raise HTTPException(404, "Camera not found")
    zone = DetectionZone(camera_id=camera_id, **body.model_dump())
    db.add(zone)
    db.commit()
    db.refresh(zone)
    _sync_zones(db, camera_id)
    return zone


@router.patch("/{zone_id}", response_model=ZoneOut)
def update_zone(
    camera_id: int,
    zone_id: int,
    body: ZoneUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("zones:write")),
):
    zone = db.query(DetectionZone).filter(
        DetectionZone.id == zone_id, DetectionZone.camera_id == camera_id
    ).first()
    if not zone:
        raise HTTPException(404, "Zone not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(zone, k, v)
    db.commit()
    db.refresh(zone)
    _sync_zones(db, camera_id)
    return zone


@router.delete("/{zone_id}")
def delete_zone(
    camera_id: int,
    zone_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("zones:write")),
):
    zone = db.query(DetectionZone).filter(
        DetectionZone.id == zone_id, DetectionZone.camera_id == camera_id
    ).first()
    if not zone:
        raise HTTPException(404, "Zone not found")
    db.delete(zone)
    db.commit()
    _sync_zones(db, camera_id)
    return {"ok": True}
