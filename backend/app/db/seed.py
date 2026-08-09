"""Seed demo users, cameras, zones, and sample events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil

import cv2

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal, engine, Base
from app.models import User, Camera, DetectionZone, Event, Alert, Incident, Recording

settings = get_settings()


def generate_sample_videos():
    """Create synthetic demo videos with moving shapes if none exist."""
    settings.SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    videos = [
        ("gate_a.mp4", (40, 40, 200), "horizontal"),
        ("parking.mp4", (30, 120, 40), "diagonal"),
        ("lobby.mp4", (180, 60, 60), "vertical"),
        ("warehouse.mp4", (20, 80, 160), "bounce"),
    ]
    for name, color, motion in videos:
        path = settings.SAMPLE_DIR / name
        if path.exists():
            continue
        w, h, fps, nframes = 960, 540, 15, 15 * 20  # 20 seconds
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(path), fourcc, fps, (w, h))
        for i in range(nframes):
            import numpy as np
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            # grid background
            frame[:] = (28, 28, 32)
            for x in range(0, w, 40):
                cv2.line(frame, (x, 0), (x, h), (40, 40, 48), 1)
            for y in range(0, h, 40):
                cv2.line(frame, (0, y), (w, y), (40, 40, 48), 1)
            t = i / fps
            if motion == "horizontal":
                cx = int((t * 80) % (w - 80)) + 40
                cy = h // 2
            elif motion == "vertical":
                cx = w // 2
                cy = int((t * 60) % (h - 80)) + 40
            elif motion == "diagonal":
                cx = int((t * 70) % (w - 80)) + 40
                cy = int((t * 40) % (h - 80)) + 40
            else:
                cx = int(w / 2 + 200 * abs((t % 4) - 2) / 2 - 100)
                cy = int(h / 2 + 100 * ((t % 3) - 1.5) / 1.5)

            # "person" blob
            cv2.ellipse(frame, (cx, cy), (18, 40), 0, 0, 360, color, -1)
            cv2.circle(frame, (cx, cy - 50), 16, color, -1)
            # occasional "vehicle"
            if int(t) % 7 == 0:
                vx = int((t * 120) % (w - 100))
                cv2.rectangle(frame, (vx, h - 100), (vx + 90, h - 60), (0, 140, 255), -1)
            # label
            cv2.putText(frame, name.replace(".mp4", "").upper(), (16, 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 210), 2)
            writer.write(frame)
        writer.release()


def seed_database(force: bool = False):
    Base.metadata.create_all(bind=engine)
    if not settings.SKIP_VIDEO_GEN:
        generate_sample_videos()
    db = SessionLocal()
    try:
        if db.query(User).count() > 0 and not force:
            return

        if force:
            for model in (Incident, Alert, Event, Recording, DetectionZone, Camera, User):
                db.query(model).delete()
            db.commit()

        users = [
            User(email="admin@aethershield.io", full_name="System Admin",
                 hashed_password=hash_password("admin123"), role="admin"),
            User(email="operator@aethershield.io", full_name="Ops Operator",
                 hashed_password=hash_password("operator123"), role="operator"),
            User(email="viewer@aethershield.io", full_name="Security Viewer",
                 hashed_password=hash_password("viewer123"), role="viewer"),
        ]
        db.add_all(users)

        cameras = [
            Camera(
                name="Gate A",
                location="Main Entrance",
                source_type="file",
                source_uri="sample-data/videos/gate_a.mp4",
                status="online",
                resolution="960x540",
                fps=15,
                map_x=0.2,
                map_y=0.35,
                ai_enabled=True,
                is_demo=True,
                enabled=True,
            ),
            Camera(
                name="Parking Lot",
                location="North Parking",
                source_type="file",
                source_uri="sample-data/videos/parking.mp4",
                status="online",
                resolution="960x540",
                fps=15,
                map_x=0.55,
                map_y=0.25,
                ai_enabled=True,
                is_demo=True,
                enabled=True,
            ),
            Camera(
                name="Lobby",
                location="Building Lobby",
                source_type="file",
                source_uri="sample-data/videos/lobby.mp4",
                status="online",
                resolution="960x540",
                fps=15,
                map_x=0.4,
                map_y=0.55,
                ai_enabled=True,
                is_demo=True,
                enabled=True,
            ),
            Camera(
                name="Warehouse",
                location="Loading Bay",
                source_type="file",
                source_uri="sample-data/videos/warehouse.mp4",
                status="online",
                resolution="960x540",
                fps=15,
                map_x=0.75,
                map_y=0.65,
                ai_enabled=True,
                is_demo=True,
                enabled=True,
            ),
        ]
        db.add_all(cameras)
        db.flush()

        zones = [
            DetectionZone(
                camera_id=cameras[0].id,
                name="Entry Gate Zone",
                shape="rectangle",
                geometry={"x": 0.15, "y": 0.2, "w": 0.55, "h": 0.55},
                sensitivity=0.7,
                enabled=True,
                trigger_classes=["person"],
                color="#ef4444",
            ),
            DetectionZone(
                camera_id=cameras[1].id,
                name="Restricted Parking",
                shape="polygon",
                geometry={"points": [
                    {"x": 0.1, "y": 0.3}, {"x": 0.8, "y": 0.25},
                    {"x": 0.85, "y": 0.8}, {"x": 0.15, "y": 0.85},
                ]},
                sensitivity=0.6,
                enabled=True,
                trigger_classes=["person", "car", "truck"],
                color="#f97316",
            ),
            DetectionZone(
                camera_id=cameras[2].id,
                name="Reception Circle",
                shape="circle",
                geometry={"cx": 0.5, "cy": 0.5, "r": 0.28},
                sensitivity=0.5,
                enabled=True,
                trigger_classes=[],
                color="#3b82f6",
            ),
        ]
        db.add_all(zones)
        db.flush()

        now = datetime.now(timezone.utc)
        sample_events = []
        specs = [
            (cameras[0].id, zones[0].id, "intrusion", "Intrusion: person in Entry Gate Zone", 0.94, "critical"),
            (cameras[0].id, None, "person", "Person detected", 0.91, "high"),
            (cameras[1].id, None, "car", "Car detected", 0.88, "medium"),
            (cameras[1].id, zones[1].id, "intrusion", "Intrusion: car in Restricted Parking", 0.86, "critical"),
            (cameras[2].id, None, "person", "Person detected", 0.97, "high"),
            (cameras[2].id, None, "backpack", "Backpack detected", 0.72, "medium"),
            (cameras[3].id, None, "person", "Person detected", 0.89, "high"),
            (cameras[3].id, None, "motion", "Motion detected", 0.65, "low"),
            (cameras[0].id, None, "bicycle", "Bicycle detected", 0.78, "low"),
            (cameras[1].id, None, "truck", "Truck detected", 0.84, "medium"),
        ]
        for i, (cid, zid, etype, label, conf, pri) in enumerate(specs):
            sample_events.append(Event(
                camera_id=cid,
                zone_id=zid,
                event_type=etype,
                label=label,
                confidence=conf,
                priority=pri,
                track_id=10 + i,
                bbox={"x": 0.3, "y": 0.25, "w": 0.2, "h": 0.4},
                timestamp=now - timedelta(minutes=5 * (i + 1), hours=i % 3),
                metadata_json={"object": etype if etype != "intrusion" else "person", "seeded": True},
            ))
        db.add_all(sample_events)
        db.flush()

        # Incidents for critical events
        for ev in sample_events:
            if ev.priority == "critical":
                db.add(Incident(event_id=ev.id, status="open", notes="Auto-created from critical alert"))
                db.add(Alert(
                    event_id=ev.id,
                    camera_id=ev.camera_id,
                    title=ev.label,
                    message=f"{ev.label} (confidence {ev.confidence:.0%})",
                    priority="critical",
                    is_active=True,
                ))

        # Link sample recordings to generated videos
        for cam in cameras:
            src = settings.BASE_DIR / cam.source_uri
            dest_dir = settings.RECORDINGS_DIR / f"camera_{cam.id}"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / "demo_segment.mp4"
            if src.exists() and not dest.exists():
                shutil.copy2(src, dest)
            if dest.exists():
                db.add(Recording(
                    camera_id=cam.id,
                    file_path=str(dest.relative_to(settings.BASE_DIR)).replace("\\", "/"),
                    start_time=now - timedelta(hours=2),
                    end_time=now - timedelta(hours=2) + timedelta(seconds=20),
                    duration_seconds=20,
                    file_size_bytes=dest.stat().st_size,
                    resolution=cam.resolution,
                ))

        db.commit()
        print("Database seeded successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database(force=True)
