from datetime import datetime, timezone
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.session import Base


def utcnow():
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    admin = "admin"
    operator = "operator"
    viewer = "viewer"


class CameraStatus(str, enum.Enum):
    online = "online"
    offline = "offline"
    recording = "recording"
    error = "error"


class EventPriority(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class IncidentStatus(str, enum.Enum):
    open = "open"
    investigating = "investigating"
    resolved = "resolved"
    false_alarm = "false_alarm"
    escalated = "escalated"


class ZoneShape(str, enum.Enum):
    rectangle = "rectangle"
    polygon = "polygon"
    circle = "circle"
    freehand = "freehand"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Site(Base):
    """A physical site that owns many cameras (HQ, Warehouse, …)."""

    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(String(50), unique=True)
    address: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    cameras = relationship("Camera", back_populates="site")


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    location: Mapped[str] = mapped_column(String(255), default="")
    source_type: Mapped[str] = mapped_column(String(50), default="file")  # file | webcam | rtsp
    source_uri: Mapped[str] = mapped_column(String(1024))  # path, index, or rtsp url
    status: Mapped[str] = mapped_column(String(50), default="offline")
    resolution: Mapped[str] = mapped_column(String(50), default="1280x720")
    fps: Mapped[float] = mapped_column(Float, default=15.0)
    is_recording: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    map_x: Mapped[float] = mapped_column(Float, default=0.5)
    map_y: Mapped[float] = mapped_column(Float, default=0.5)
    thumbnail_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    site = relationship("Site", back_populates="cameras")
    zones = relationship("DetectionZone", back_populates="camera", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="camera", cascade="all, delete-orphan")
    recordings = relationship("Recording", back_populates="camera", cascade="all, delete-orphan")


class DetectionZone(Base):
    __tablename__ = "detection_zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    shape: Mapped[str] = mapped_column(String(50), default="rectangle")
    # Normalized 0-1 coordinates: rect={x,y,w,h}, circle={cx,cy,r}, polygon={points:[{x,y}]}
    geometry: Mapped[dict] = mapped_column(JSON)
    sensitivity: Mapped[float] = mapped_column(Float, default=0.5)  # 0-1
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    trigger_classes: Mapped[list] = mapped_column(JSON, default=list)  # empty = all
    color: Mapped[str] = mapped_column(String(20), default="#ef4444")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    camera = relationship("Camera", back_populates="zones")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("detection_zones.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)  # person, vehicle, intrusion, motion, fire...
    label: Mapped[str] = mapped_column(String(255))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    priority: Mapped[str] = mapped_column(String(50), default="medium", index=True)
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {x,y,w,h} normalized
    snapshot_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)

    camera = relationship("Camera", back_populates="events")
    incident = relationship("Incident", back_populates="event", uselist=False)


class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    file_path: Mapped[str] = mapped_column(String(1024))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    resolution: Mapped[str] = mapped_column(String(50), default="1280x720")

    camera = relationship("Camera", back_populates="recordings")


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(String(50), default="open", index=True)
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    event = relationship("Event", back_populates="incident")


class AlertPolicy(Base):
    """Stored alert rule evaluated against detection events."""

    __tablename__ = "alert_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    # zone_after_hours | loitering | unknown_face
    rule_type: Mapped[str] = mapped_column(String(50), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    priority: Mapped[str] = mapped_column(String(50), default="high")
    notify_channel: Mapped[str] = mapped_column(String(20), default="webhook")  # webhook | email
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"), nullable=True)
    camera_id: Mapped[int | None] = mapped_column(ForeignKey("cameras.id"), nullable=True)
    policy_id: Mapped[int | None] = mapped_column(ForeignKey("alert_policies.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(50), default="high")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    """Operator audit trail: login, alert ack, incident status, policy edits."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_email: Mapped[str] = mapped_column(String(255), default="")
    action: Mapped[str] = mapped_column(String(100), index=True)
    target: Mapped[str] = mapped_column(String(255), default="")
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class NotificationOutbox(Base):
    """Simulated delivery queue. Nothing is sent to the public internet."""

    __tablename__ = "notification_outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[int | None] = mapped_column(ForeignKey("alerts.id"), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(20))  # webhook | email
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending | sent
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
