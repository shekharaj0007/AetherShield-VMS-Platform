from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, EmailStr, Field


# ── Auth ──────────────────────────────────────────────
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: str = "viewer"


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


# ── Cameras ───────────────────────────────────────────
class CameraCreate(BaseModel):
    name: str
    location: str = ""
    source_type: str = "file"  # file | webcam | rtsp | http
    source_uri: str
    resolution: str = "1280x720"
    fps: float = 15.0
    ai_enabled: bool = True
    map_x: float = 0.5
    map_y: float = 0.5
    is_demo: bool = False
    enabled: bool = True


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    source_type: Optional[str] = None
    source_uri: Optional[str] = None
    ai_enabled: Optional[bool] = None
    is_recording: Optional[bool] = None
    map_x: Optional[float] = None
    map_y: Optional[float] = None
    status: Optional[str] = None
    enabled: Optional[bool] = None
    is_demo: Optional[bool] = None


class CameraOut(BaseModel):
    id: int
    name: str
    location: str
    source_type: str
    source_uri: str
    status: str
    resolution: str
    fps: float
    is_recording: bool
    ai_enabled: bool
    map_x: float
    map_y: float
    thumbnail_path: Optional[str] = None
    is_demo: bool = False
    enabled: bool = True

    class Config:
        from_attributes = True


class DemoToggle(BaseModel):
    enabled: bool


class RemoteCameraConnect(BaseModel):
    name: str
    location: str = "Remote Device"
    source_type: str = "rtsp"  # rtsp | http | webcam
    source_uri: str
    ai_enabled: bool = True


# ── Zones ─────────────────────────────────────────────
class ZoneCreate(BaseModel):
    name: str
    shape: str = "rectangle"
    geometry: dict
    sensitivity: float = Field(default=0.5, ge=0, le=1)
    enabled: bool = True
    trigger_classes: list[str] = []
    color: str = "#ef4444"


class ZoneUpdate(BaseModel):
    name: Optional[str] = None
    shape: Optional[str] = None
    geometry: Optional[dict] = None
    sensitivity: Optional[float] = None
    enabled: Optional[bool] = None
    trigger_classes: Optional[list[str]] = None
    color: Optional[str] = None


class ZoneOut(BaseModel):
    id: int
    camera_id: int
    name: str
    shape: str
    geometry: dict
    sensitivity: float
    enabled: bool
    trigger_classes: list
    color: str

    class Config:
        from_attributes = True


# ── Events ────────────────────────────────────────────
class EventOut(BaseModel):
    id: int
    camera_id: int
    zone_id: Optional[int] = None
    event_type: str
    label: str
    confidence: float
    priority: str
    track_id: Optional[int] = None
    bbox: Optional[dict] = None
    snapshot_path: Optional[str] = None
    metadata_json: Optional[dict] = None
    timestamp: datetime
    acknowledged: bool
    camera_name: Optional[str] = None

    class Config:
        from_attributes = True


class EventSearchQuery(BaseModel):
    query: str
    camera_id: Optional[int] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    limit: int = 50


# ── Incidents ─────────────────────────────────────────
class IncidentUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    assigned_to: Optional[int] = None


class IncidentOut(BaseModel):
    id: int
    event_id: int
    status: str
    assigned_to: Optional[int] = None
    notes: str
    created_at: datetime
    updated_at: datetime
    event: Optional[EventOut] = None

    class Config:
        from_attributes = True


# ── Recordings ────────────────────────────────────────
class RecordingOut(BaseModel):
    id: int
    camera_id: int
    file_path: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: float
    file_size_bytes: int
    resolution: str

    class Config:
        from_attributes = True


# ── Dashboard ─────────────────────────────────────────
class DashboardStats(BaseModel):
    total_cameras: int
    online_cameras: int
    offline_cameras: int
    today_detections: int
    active_alerts: int
    storage_used_gb: float
    storage_total_gb: float
    storage_days_remaining: Optional[float] = None
    cpu_percent: float
    memory_percent: float
    detections_by_type: dict[str, int]
    weekly_detections: list[dict[str, Any]]
    recent_events: list[EventOut]
    camera_health: list[CameraOut]
    active_alerts_list: list[dict[str, Any]]
    insights: dict[str, Any]


# ── Alerts ────────────────────────────────────────────
class AlertOut(BaseModel):
    id: int
    event_id: Optional[int] = None
    camera_id: Optional[int] = None
    title: str
    message: str
    priority: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── AI Chat / Summary ─────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    camera_id: Optional[int] = None


class ChatResponse(BaseModel):
    reply: str
    events: list[EventOut] = []
    sources: list[str] = []


class SummaryResponse(BaseModel):
    period: str
    summary_text: str
    stats: dict[str, Any]
    highlights: list[str]
