"""Camera stream manager — live frames, AI, recording, MJPEG."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable
import json

import cv2
import numpy as np

from app.core.config import get_settings
from app.ai.detector import (
    detect_frame,
    draw_detections,
    filter_zone_intrusions,
    Detection,
    PRIORITY_MAP,
)
from app.ai.faces import recognize_in_frame
from app.ai.plates import extract_plates_from_detections
from app.ai import heatmap as heatmap_svc

settings = get_settings()


@dataclass
class StreamStats:
    fps: float = 0.0
    frame_count: int = 0
    last_detections: list = field(default_factory=list)
    status: str = "offline"
    last_error: Optional[str] = None


class CameraStream:
    def __init__(
        self,
        camera_id: int,
        source_type: str,
        source_uri: str,
        ai_enabled: bool = True,
        on_event: Optional[Callable] = None,
    ):
        self.camera_id = camera_id
        self.source_type = source_type
        self.source_uri = source_uri
        self.ai_enabled = ai_enabled
        self.on_event = on_event
        self.zones: list[dict] = []
        self.stats = StreamStats()
        self._cap: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._frame: Optional[np.ndarray] = None
        self._annotated: Optional[np.ndarray] = None
        self._writer: Optional[cv2.VideoWriter] = None
        self._segment_start: Optional[datetime] = None
        self._segment_path: Optional[Path] = None
        self._last_detect_ts = 0.0
        self._plate_ts = 0.0
        self._event_cooldown: dict[str, float] = {}
        self.recording = True
        self._last_faces: list = []
        self._last_plates: list = []

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name=f"cam-{self.camera_id}")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        self._close_writer()
        if self._cap:
            self._cap.release()
            self._cap = None
        self.stats.status = "offline"

    def update_zones(self, zones: list[dict]):
        self.zones = zones

    def get_jpeg(self, annotated: bool = True, quality: int | None = None) -> Optional[bytes]:
        with self._lock:
            frame = self._annotated if annotated and self._annotated is not None else self._frame
            if frame is None:
                return None
            q = quality or settings.JPEG_QUALITY
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), q])
            return buf.tobytes() if ok else None

    def get_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return None if self._frame is None else self._frame.copy()

    def _open_capture(self) -> bool:
        if self.source_type == "webcam":
            idx = int(self.source_uri) if str(self.source_uri).isdigit() else 0
            # CAP_DSHOW is more reliable on Windows
            self._cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if not self._cap.isOpened():
                self._cap = cv2.VideoCapture(idx)
        elif self.source_type in ("rtsp", "http"):
            # Remote device: RTSP IP cam, phone IP Webcam HTTP, etc.
            self._cap = cv2.VideoCapture(self.source_uri)
            # Prefer FFMPEG backend hints for network streams
            if not self._cap.isOpened():
                self._cap = cv2.VideoCapture(self.source_uri, cv2.CAP_FFMPEG)
        else:
            # file
            path = self.source_uri
            if self.source_type == "file":
                p = Path(path)
                if not p.is_absolute():
                    p = settings.BASE_DIR / path
                path = str(p)
            self._cap = cv2.VideoCapture(path)

        if not self._cap or not self._cap.isOpened():
            self.stats.status = "error"
            self.stats.last_error = f"Cannot open source: {self.source_uri}"
            return False
        self.stats.status = "online"
        return True

    def _loop(self):
        if not self._open_capture():
            return

        fps_target = settings.DEFAULT_FPS
        frame_interval = 1.0 / fps_target
        fps_counter = 0
        fps_timer = time.time()
        is_file = self.source_type == "file"
        is_network = self.source_type in ("rtsp", "http")

        while not self._stop.is_set():
            t0 = time.time()
            ok, frame = self._cap.read()
            if not ok or frame is None:
                if is_file:
                    # Loop sample videos for continuous "live" demo
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                self.stats.status = "offline" if not is_network else "error"
                time.sleep(1)
                if not self._open_capture():
                    time.sleep(2)
                continue

            self.stats.status = "recording" if self.recording else "online"
            detections: list[Detection] = []
            now = time.time()

            if self.ai_enabled and (now - self._last_detect_ts) * 1000 >= settings.DETECTION_INTERVAL_MS:
                self._last_detect_ts = now
                detections = detect_frame(frame, track=True)

                # Heatmap from detection centers
                pts = [((d.bbox[0] + d.bbox[2]) / 2, (d.bbox[1] + d.bbox[3]) / 2) for d in detections]
                if pts:
                    heatmap_svc.add_points(self.camera_id, pts)

                # Face recognition on persons
                try:
                    self._last_faces = recognize_in_frame(frame, detections)
                except Exception:
                    self._last_faces = []

                # LPR on vehicles (throttled — OCR is expensive)
                if now - self._plate_ts > 4.0:
                    self._plate_ts = now
                    try:
                        self._last_plates = extract_plates_from_detections(frame, detections)
                    except Exception:
                        self._last_plates = []

                self.stats.last_detections = [
                    {
                        "label": d.label,
                        "confidence": d.confidence,
                        "bbox": {"x1": d.bbox[0], "y1": d.bbox[1], "x2": d.bbox[2], "y2": d.bbox[3]},
                        "track_id": d.track_id,
                        "priority": d.priority,
                    }
                    for d in detections
                ]
                self._emit_events(frame, detections)

            annotated = draw_detections(frame, detections, self.zones) if self.ai_enabled else frame
            if self.ai_enabled:
                annotated = self._draw_faces_plates(annotated)

            with self._lock:
                self._frame = frame
                self._annotated = annotated

            if self.recording:
                self._write_frame(frame)

            fps_counter += 1
            self.stats.frame_count += 1
            if time.time() - fps_timer >= 1.0:
                self.stats.fps = fps_counter / (time.time() - fps_timer)
                fps_counter = 0
                fps_timer = time.time()

            elapsed = time.time() - t0
            sleep_for = frame_interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)

        self._close_writer()

    def _emit_events(self, frame: np.ndarray, detections: list[Detection]):
        if not self.on_event:
            return
        now = time.time()
        # Zone intrusions take priority
        hits = filter_zone_intrusions(detections, self.zones)
        emitted_keys = set()

        for d, zone in hits:
            key = f"intrusion:{zone.get('id')}:{d.label}:{d.track_id}"
            if now - self._event_cooldown.get(key, 0) < 8:
                continue
            self._event_cooldown[key] = now
            emitted_keys.add(key)
            snap = self._save_snapshot(frame, d)
            self.on_event({
                "camera_id": self.camera_id,
                "zone_id": zone.get("id"),
                "event_type": "intrusion",
                "label": f"Intrusion: {d.label} in {zone.get('name', 'zone')}",
                "confidence": d.confidence,
                "priority": "critical",
                "track_id": d.track_id,
                "bbox": {"x": d.bbox[0], "y": d.bbox[1], "w": d.bbox[2] - d.bbox[0], "h": d.bbox[3] - d.bbox[1]},
                "snapshot_path": snap,
                "metadata_json": {"zone_name": zone.get("name"), "object": d.label},
            })

        # Regular object detections (cooldown per track/label)
        for d in detections:
            if d.label == "motion":
                key = f"motion:{d.label}"
            else:
                key = f"obj:{d.label}:{d.track_id}"
            if key in emitted_keys:
                continue
            if now - self._event_cooldown.get(key, 0) < 12:
                continue
            self._event_cooldown[key] = now
            snap = self._save_snapshot(frame, d)
            self.on_event({
                "camera_id": self.camera_id,
                "zone_id": None,
                "event_type": d.label,
                "label": f"{d.label.capitalize()} detected",
                "confidence": d.confidence,
                "priority": d.priority,
                "track_id": d.track_id,
                "bbox": {"x": d.bbox[0], "y": d.bbox[1], "w": d.bbox[2] - d.bbox[0], "h": d.bbox[3] - d.bbox[1]},
                "snapshot_path": snap,
                "metadata_json": {"object": d.label},
            })

        # Face identity events
        for face in self._last_faces:
            key = f"face:{face.name}:{face.category}"
            if now - self._event_cooldown.get(key, 0) < 15:
                continue
            self._event_cooldown[key] = now
            priority = "critical" if face.category == "blacklist" else ("high" if face.category == "unknown" else "medium")
            label = (
                f"Blacklist match: {face.name}" if face.category == "blacklist"
                else f"Known person: {face.name}" if face.category == "known"
                else f"Unknown face: {face.name}"
            )
            self.on_event({
                "camera_id": self.camera_id,
                "zone_id": None,
                "event_type": "face",
                "label": label,
                "confidence": float(face.confidence) if face.confidence > 0 else 0.7,
                "priority": priority,
                "track_id": None,
                "bbox": {
                    "x": face.bbox[0], "y": face.bbox[1],
                    "w": face.bbox[2] - face.bbox[0], "h": face.bbox[3] - face.bbox[1],
                },
                "snapshot_path": None,
                "metadata_json": {"face_name": face.name, "face_category": face.category},
            })

        # License plate events
        for plate in self._last_plates:
            key = f"plate:{plate.plate}"
            if now - self._event_cooldown.get(key, 0) < 20:
                continue
            self._event_cooldown[key] = now
            self.on_event({
                "camera_id": self.camera_id,
                "zone_id": None,
                "event_type": "plate",
                "label": f"License plate: {plate.plate}",
                "confidence": plate.confidence,
                "priority": "medium",
                "track_id": None,
                "bbox": {
                    "x": plate.bbox[0], "y": plate.bbox[1],
                    "w": plate.bbox[2] - plate.bbox[0], "h": plate.bbox[3] - plate.bbox[1],
                },
                "snapshot_path": None,
                "metadata_json": {"plate": plate.plate},
            })

    def _draw_faces_plates(self, frame: np.ndarray) -> np.ndarray:
        out = frame
        h, w = out.shape[:2]
        for face in self._last_faces:
            x1, y1, x2, y2 = face.bbox
            color = (0, 0, 255) if face.category == "blacklist" else ((0, 200, 255) if face.category == "unknown" else (0, 220, 120))
            pt1 = (int(x1 * w), int(y1 * h))
            pt2 = (int(x2 * w), int(y2 * h))
            cv2.rectangle(out, pt1, pt2, color, 2)
            cv2.putText(out, face.name[:28], (pt1[0], max(pt1[1] - 6, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
        for plate in self._last_plates:
            x1, y1, x2, y2 = plate.bbox
            pt1 = (int(x1 * w), int(y1 * h))
            pt2 = (int(x2 * w), int(y2 * h))
            cv2.rectangle(out, pt1, pt2, (0, 165, 255), 2)
            cv2.putText(out, plate.plate, (pt1[0], max(pt1[1] - 6, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1, cv2.LINE_AA)
        return out

    def _save_snapshot(self, frame: np.ndarray, d: Detection) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        path = settings.SNAPSHOTS_DIR / f"cam{self.camera_id}_{ts}.jpg"
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = d.bbox
        annotated = frame.copy()
        cv2.rectangle(
            annotated,
            (int(x1 * w), int(y1 * h)),
            (int(x2 * w), int(y2 * h)),
            (0, 0, 255),
            2,
        )
        cv2.imwrite(str(path), annotated)
        return str(path.relative_to(settings.BASE_DIR)).replace("\\", "/")

    def _write_frame(self, frame: np.ndarray):
        now = datetime.now(timezone.utc)
        if self._writer is None or self._segment_start is None:
            self._open_writer(frame, now)
            return
        elapsed = (now - self._segment_start).total_seconds()
        if elapsed >= settings.RECORD_SEGMENT_SECONDS:
            self._close_writer()
            self._open_writer(frame, now)
            return
        self._writer.write(frame)

    def _open_writer(self, frame: np.ndarray, start: datetime):
        h, w = frame.shape[:2]
        cam_dir = settings.RECORDINGS_DIR / f"camera_{self.camera_id}"
        cam_dir.mkdir(parents=True, exist_ok=True)
        fname = start.strftime("%Y%m%d_%H%M%S") + ".mp4"
        path = cam_dir / fname
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._writer = cv2.VideoWriter(str(path), fourcc, float(settings.DEFAULT_FPS), (w, h))
        self._segment_start = start
        self._segment_path = path

    def _close_writer(self):
        if self._writer is not None:
            self._writer.release()
            # Register recording via callback metadata file for pickup
            if self._segment_path and self._segment_start:
                end = datetime.now(timezone.utc)
                meta = {
                    "camera_id": self.camera_id,
                    "file_path": str(self._segment_path.relative_to(settings.BASE_DIR)).replace("\\", "/"),
                    "start_time": self._segment_start.isoformat(),
                    "end_time": end.isoformat(),
                    "duration_seconds": (end - self._segment_start).total_seconds(),
                    "file_size_bytes": self._segment_path.stat().st_size if self._segment_path.exists() else 0,
                }
                meta_path = self._segment_path.with_suffix(".json")
                meta_path.write_text(json.dumps(meta), encoding="utf-8")
            self._writer = None
            self._segment_start = None
            self._segment_path = None


class StreamManager:
    def __init__(self):
        self._streams: dict[int, CameraStream] = {}
        self._lock = threading.Lock()
        self.on_event: Optional[Callable] = None

    def set_event_handler(self, handler: Callable):
        self.on_event = handler
        for s in self._streams.values():
            s.on_event = handler

    def start_camera(self, camera_id: int, source_type: str, source_uri: str, ai_enabled: bool = True, zones: list | None = None):
        with self._lock:
            if camera_id in self._streams:
                self._streams[camera_id].stop()
            stream = CameraStream(camera_id, source_type, source_uri, ai_enabled, self.on_event)
            if zones:
                stream.update_zones(zones)
            self._streams[camera_id] = stream
            stream.start()

    def stop_camera(self, camera_id: int):
        with self._lock:
            s = self._streams.pop(camera_id, None)
            if s:
                s.stop()

    def stop_all(self):
        with self._lock:
            for s in self._streams.values():
                s.stop()
            self._streams.clear()

    def get(self, camera_id: int) -> Optional[CameraStream]:
        return self._streams.get(camera_id)

    def update_zones(self, camera_id: int, zones: list[dict]):
        s = self._streams.get(camera_id)
        if s:
            s.update_zones(zones)

    def list_stats(self) -> dict[int, StreamStats]:
        return {cid: s.stats for cid, s in self._streams.items()}


stream_manager = StreamManager()
