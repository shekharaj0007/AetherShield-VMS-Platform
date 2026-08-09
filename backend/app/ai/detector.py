"""YOLOv11 detection + ByteTrack tracking + zone intrusion."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from app.core.config import get_settings

settings = get_settings()

# COCO + custom priority mapping
PRIORITY_MAP = {
    "person": "high",
    "car": "medium",
    "truck": "medium",
    "bus": "medium",
    "motorcycle": "medium",
    "bicycle": "low",
    "dog": "medium",
    "cat": "low",
    "fire": "critical",
    "smoke": "critical",
    "bag": "medium",
    "backpack": "medium",
    "knife": "critical",
    "gun": "critical",
    "weapon": "critical",
    "intrusion": "critical",
    "motion": "low",
}

COLOR_MAP = {
    "person": "#ef4444",
    "car": "#f97316",
    "truck": "#f97316",
    "bus": "#f97316",
    "motorcycle": "#f97316",
    "bicycle": "#eab308",
    "dog": "#a855f7",
    "fire": "#3b82f6",
    "smoke": "#3b82f6",
    "intrusion": "#dc2626",
    "motion": "#22c55e",
}

# Classes we care about from COCO
TARGET_CLASSES = {
    "person", "bicycle", "car", "motorcycle", "bus", "truck",
    "dog", "cat", "backpack", "handbag", "suitcase",
}


@dataclass
class Detection:
    label: str
    confidence: float
    bbox: tuple[float, float, float, float]  # x1,y1,x2,y2 normalized 0-1
    track_id: Optional[int] = None
    priority: str = "medium"


@dataclass
class DetectorState:
    model: object = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    loaded: bool = False
    load_error: Optional[str] = None


_state = DetectorState()


def _load_model():
    with _state.lock:
        if _state.loaded:
            return
        try:
            from ultralytics import YOLO
            _state.model = YOLO(settings.YOLO_MODEL)
            _state.loaded = True
            _state.load_error = None
        except Exception as e:
            _state.load_error = str(e)
            _state.loaded = False


def ensure_model():
    if not _state.loaded:
        _load_model()
    return _state.model


def point_in_zone(cx: float, cy: float, shape: str, geometry: dict) -> bool:
    """Check if normalized point is inside zone geometry."""
    if shape == "rectangle":
        x, y, w, h = geometry.get("x", 0), geometry.get("y", 0), geometry.get("w", 0), geometry.get("h", 0)
        return x <= cx <= x + w and y <= cy <= y + h
    if shape == "circle":
        rcx, rcy, r = geometry.get("cx", 0.5), geometry.get("cy", 0.5), geometry.get("r", 0.1)
        return ((cx - rcx) ** 2 + (cy - rcy) ** 2) ** 0.5 <= r
    if shape in ("polygon", "freehand"):
        points = geometry.get("points", [])
        if len(points) < 3:
            return False
        contour = np.array([[p["x"], p["y"]] for p in points], dtype=np.float32)
        return cv2.pointPolygonTest(contour, (cx, cy), False) >= 0
    return False


def bbox_center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return (x1 + x2) / 2, (y1 + y2) / 2


def detect_frame(
    frame: np.ndarray,
    conf: float | None = None,
    track: bool = True,
) -> list[Detection]:
    """Run YOLO (+ optional tracking) on a BGR frame. Returns normalized detections."""
    model = ensure_model()
    if model is None:
        return _motion_fallback(frame)

    h, w = frame.shape[:2]
    conf = conf if conf is not None else settings.DETECTION_CONFIDENCE
    detections: list[Detection] = []

    try:
        if track and settings.TRACK_ENABLED:
            results = model.track(frame, conf=conf, persist=True, verbose=False)
        else:
            results = model.predict(frame, conf=conf, verbose=False)
    except Exception:
        try:
            results = model.predict(frame, conf=conf, verbose=False)
        except Exception:
            return _motion_fallback(frame)

    try:
        for r in results:
            if r.boxes is None:
                continue
            names = r.names
            for box in r.boxes:
                cls_id = int(box.cls[0])
                label = names.get(cls_id, str(cls_id))
                if label not in TARGET_CLASSES:
                    continue
                score = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                tid = None
                if box.id is not None:
                    tid = int(box.id[0])
                detections.append(
                    Detection(
                        label=label,
                        confidence=score,
                        bbox=(x1 / w, y1 / h, x2 / w, y2 / h),
                        track_id=tid,
                        priority=PRIORITY_MAP.get(label, "medium"),
                    )
                )
    except Exception:
        return _motion_fallback(frame)

    return detections


_prev_gray: dict[int, np.ndarray] = {}


def _motion_fallback(frame: np.ndarray, camera_id: int = 0) -> list[Detection]:
    """Simple frame-diff motion when YOLO unavailable."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)
    prev = _prev_gray.get(camera_id)
    _prev_gray[camera_id] = gray
    if prev is None:
        return []
    delta = cv2.absdiff(prev, gray)
    thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
    thresh = cv2.dilate(thresh, None, iterations=2)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = frame.shape[:2]
    dets = []
    for c in contours:
        if cv2.contourArea(c) < 800:
            continue
        x, y, bw, bh = cv2.boundingRect(c)
        dets.append(
            Detection(
                label="motion",
                confidence=0.6,
                bbox=(x / w, y / h, (x + bw) / w, (y + bh) / h),
                priority="low",
            )
        )
        if len(dets) >= 5:
            break
    return dets


def draw_detections(
    frame: np.ndarray,
    detections: list[Detection],
    zones: list[dict] | None = None,
) -> np.ndarray:
    """Overlay boxes, track IDs, and zones on frame."""
    out = frame.copy()
    h, w = out.shape[:2]

    if zones:
        for z in zones:
            if not z.get("enabled", True):
                continue
            color = _hex_to_bgr(z.get("color", "#ef4444"))
            geom = z.get("geometry", {})
            shape = z.get("shape", "rectangle")
            if shape == "rectangle":
                x1 = int(geom.get("x", 0) * w)
                y1 = int(geom.get("y", 0) * h)
                x2 = int((geom.get("x", 0) + geom.get("w", 0)) * w)
                y2 = int((geom.get("y", 0) + geom.get("h", 0)) * h)
                overlay = out.copy()
                cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
                cv2.addWeighted(overlay, 0.15, out, 0.85, 0, out)
                cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
                cv2.putText(out, z.get("name", "Zone"), (x1, max(y1 - 6, 12)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
            elif shape == "circle":
                cx = int(geom.get("cx", 0.5) * w)
                cy = int(geom.get("cy", 0.5) * h)
                r = int(geom.get("r", 0.1) * min(w, h))
                overlay = out.copy()
                cv2.circle(overlay, (cx, cy), r, color, -1)
                cv2.addWeighted(overlay, 0.15, out, 0.85, 0, out)
                cv2.circle(out, (cx, cy), r, color, 2)
            elif shape in ("polygon", "freehand"):
                pts = geom.get("points", [])
                if len(pts) >= 3:
                    arr = np.array([[int(p["x"] * w), int(p["y"] * h)] for p in pts], np.int32)
                    overlay = out.copy()
                    cv2.fillPoly(overlay, [arr], color)
                    cv2.addWeighted(overlay, 0.15, out, 0.85, 0, out)
                    cv2.polylines(out, [arr], True, color, 2)

    for d in detections:
        x1, y1, x2, y2 = d.bbox
        pt1 = (int(x1 * w), int(y1 * h))
        pt2 = (int(x2 * w), int(y2 * h))
        color = _hex_to_bgr(COLOR_MAP.get(d.label, "#22c55e"))
        cv2.rectangle(out, pt1, pt2, color, 2)
        tag = d.label
        if d.track_id is not None:
            tag = f"{d.label} #{d.track_id}"
        tag = f"{tag} {d.confidence:.0%}"
        cv2.putText(out, tag, (pt1[0], max(pt1[1] - 6, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
    return out


def _hex_to_bgr(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return (0, 255, 0)
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return (b, g, r)


def filter_zone_intrusions(
    detections: list[Detection],
    zones: list[dict],
) -> list[tuple[Detection, dict]]:
    """Return (detection, zone) pairs that trigger intrusion."""
    hits = []
    for z in zones:
        if not z.get("enabled", True):
            continue
        triggers = z.get("trigger_classes") or []
        sens = float(z.get("sensitivity", 0.5))
        min_conf = 0.3 + (1 - sens) * 0.5  # sensitivity ↑ → lower conf threshold
        for d in detections:
            if triggers and d.label not in triggers and d.label != "motion":
                continue
            if d.confidence < min_conf:
                continue
            cx, cy = bbox_center(d.bbox)
            if point_in_zone(cx, cy, z.get("shape", "rectangle"), z.get("geometry", {})):
                hits.append((d, z))
    return hits
