"""AetherShield VMS — FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.session import SessionLocal, Base, engine
from app.db.seed import seed_database
from app.db.migrate import ensure_camera_columns
from app.models import Event, Alert, Incident, Camera, DetectionZone
from app.services.stream_manager import stream_manager
from app.ai.faces import seed_demo_faces
from app.api import auth, cameras, zones, events, streaming, dashboard, incidents, reports, advanced

settings = get_settings()
_main_loop: asyncio.AbstractEventLoop | None = None


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def broadcast_threadsafe(self, message: dict):
        if _main_loop and _main_loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(message), _main_loop)


ws_manager = ConnectionManager()


def handle_detection_event(payload: dict):
    """Called from stream threads — persist event + alert + push WS."""
    db = SessionLocal()
    event_id = None
    try:
        event = Event(
            camera_id=payload["camera_id"],
            zone_id=payload.get("zone_id"),
            event_type=payload["event_type"],
            label=payload["label"],
            confidence=payload.get("confidence", 0),
            priority=payload.get("priority", "medium"),
            track_id=payload.get("track_id"),
            bbox=payload.get("bbox"),
            snapshot_path=payload.get("snapshot_path"),
            metadata_json=payload.get("metadata_json"),
            timestamp=datetime.now(timezone.utc),
        )
        db.add(event)
        db.flush()
        event_id = event.id

        if event.priority in ("critical", "high"):
            alert = Alert(
                event_id=event.id,
                camera_id=event.camera_id,
                title=event.label,
                message=f"{event.label} ({event.confidence:.0%})",
                priority=event.priority,
                is_active=True,
            )
            db.add(alert)
            if event.priority == "critical":
                existing = db.query(Incident).filter(Incident.event_id == event.id).first()
                if not existing:
                    db.add(Incident(event_id=event.id, status="open"))

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Event persist error: {e}")
    finally:
        db.close()

    if payload.get("priority") in ("critical", "high") or payload.get("event_type") in ("face", "plate", "intrusion"):
        ws_manager.broadcast_threadsafe({
            "type": "alert",
            "event_id": event_id,
            "camera_id": payload.get("camera_id"),
            "title": payload.get("label"),
            "priority": payload.get("priority"),
            "event_type": payload.get("event_type"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _main_loop
    _main_loop = asyncio.get_running_loop()
    Base.metadata.create_all(bind=engine)
    ensure_camera_columns()
    seed_database(force=False)
    seed_demo_faces()
    stream_manager.set_event_handler(handle_detection_event)

    db = SessionLocal()
    try:
        cams = db.query(Camera).all()
        started = 0
        for cam in cams:
            if not getattr(cam, "enabled", True):
                cam.status = "offline"
                continue
            if started >= settings.MAX_LIVE_CAMERAS:
                cam.status = "offline"
                continue
            # Free-tier / low-memory: disable YOLO to stay under 512MB
            ai_on = bool(cam.ai_enabled and settings.AI_ENABLED)
            zones_list = db.query(DetectionZone).filter(DetectionZone.camera_id == cam.id).all()
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
                for z in zones_list
            ]
            stream_manager.start_camera(
                cam.id, cam.source_type, cam.source_uri, ai_on, payload
            )
            cam.status = "online"
            started += 1
        db.commit()
    finally:
        db.close()

    print(
        f"{settings.APP_NAME} v{settings.APP_VERSION} started "
        f"(cameras={started}, ai={settings.AI_ENABLED})"
    )
    yield
    stream_manager.stop_all()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise AI Video Management System",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(cameras.router)
app.include_router(zones.router)
app.include_router(events.router)
app.include_router(streaming.router)
app.include_router(dashboard.router)
app.include_router(incidents.router)
app.include_router(reports.router)
app.include_router(advanced.router)


@app.get("/")
def root():
    """Helpful landing — this service is the API, not the React UI."""
    return {
        "app": settings.APP_NAME,
        "message": "This is the API backend. Open the frontend UI instead.",
        "frontend": "https://aethershield-ui.onrender.com",
        "docs": "/docs",
        "health": "/api/health",
        "login_demo": {
            "email": "admin@aethershield.io",
            "password": "admin123",
        },
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "ai_enabled": settings.AI_ENABLED,
        "max_live_cameras": settings.MAX_LIVE_CAMERAS,
    }


@app.websocket("/ws/alerts")
async def alerts_ws(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
