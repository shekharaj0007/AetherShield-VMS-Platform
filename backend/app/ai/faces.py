"""Face recognition — known / unknown / blacklist using OpenCV embeddings."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from app.core.config import get_settings

settings = get_settings()
FACES_DIR = settings.STORAGE_DIR / "faces"
FACES_DIR.mkdir(parents=True, exist_ok=True)
INDEX_PATH = FACES_DIR / "index.json"

_lock = threading.Lock()
_cascade = None


@dataclass
class FaceMatch:
    name: str
    category: str  # known | unknown | blacklist
    confidence: float
    bbox: tuple[float, float, float, float]  # normalized xyxy in full frame


def _get_cascade():
    global _cascade
    if _cascade is None:
        path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _cascade = cv2.CascadeClassifier(path)
    return _cascade


def _embed(face_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (64, 64), interpolation=cv2.INTER_AREA)
    gray = cv2.equalizeHist(gray)
    vec = gray.astype(np.float32).flatten()
    norm = np.linalg.norm(vec) + 1e-6
    return vec / norm


def _load_index() -> list[dict]:
    if not INDEX_PATH.exists():
        return []
    try:
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_index(entries: list[dict]):
    INDEX_PATH.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def list_faces() -> list[dict]:
    return _load_index()


def enroll_face(name: str, category: str, image_bytes: bytes) -> dict:
    """Enroll a face from uploaded image bytes. category: known|blacklist"""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Invalid image")
    faces = detect_faces_in_frame(img)
    if not faces:
        # use center crop as fallback
        h, w = img.shape[:2]
        side = min(h, w) // 2
        y1, x1 = (h - side) // 2, (w - side) // 2
        crop = img[y1 : y1 + side, x1 : x1 + side]
    else:
        x1, y1, x2, y2 = faces[0]["px"]
        crop = img[y1:y2, x1:x2]
    if crop.size == 0:
        raise ValueError("Could not extract face")

    safe = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
    cat_dir = FACES_DIR / (category if category in ("known", "blacklist") else "known")
    cat_dir.mkdir(parents=True, exist_ok=True)
    abs_path = cat_dir / f"{safe}.jpg"
    cv2.imwrite(str(abs_path), crop)
    emb = _embed(crop).tolist()

    with _lock:
        entries = [e for e in _load_index() if e.get("name", "").lower() != name.lower()]
        entry = {
            "name": name,
            "category": category if category in ("known", "blacklist") else "known",
            "path": str(Path("storage") / "faces" / category / f"{safe}.jpg").replace("\\", "/"),
            "embedding": emb,
        }
        entries.append(entry)
        _save_index(entries)
    return {"name": entry["name"], "category": entry["category"], "path": entry["path"]}


def delete_face(name: str) -> bool:
    with _lock:
        entries = _load_index()
        keep = []
        deleted = False
        for e in entries:
            if e.get("name", "").lower() == name.lower():
                deleted = True
                p = settings.BASE_DIR / e.get("path", "")
                if p.exists():
                    p.unlink(missing_ok=True)
            else:
                keep.append(e)
        _save_index(keep)
        return deleted


def detect_faces_in_frame(frame: np.ndarray, person_bbox: tuple | None = None) -> list[dict]:
    """Return pixel face boxes. Optionally restrict to person bbox (xyxy norm)."""
    h, w = frame.shape[:2]
    roi = frame
    ox, oy = 0, 0
    if person_bbox:
        x1 = int(person_bbox[0] * w)
        y1 = int(person_bbox[1] * h)
        x2 = int(person_bbox[2] * w)
        y2 = int(person_bbox[3] * h)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        roi = frame[y1:y2, x1:x2]
        ox, oy = x1, y1
        if roi.size == 0:
            return []
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    cascade = _get_cascade()
    dets = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))
    out = []
    for (x, y, bw, bh) in dets:
        out.append({"px": (ox + x, oy + y, ox + x + bw, oy + y + bh)})
    return out


def match_face(face_bgr: np.ndarray, threshold: float = 0.72) -> FaceMatch:
    emb = _embed(face_bgr)
    entries = _load_index()
    best_name = "Unknown Person"
    best_cat = "unknown"
    best_score = -1.0
    for e in entries:
        ref = np.array(e.get("embedding", []), dtype=np.float32)
        if ref.size == 0:
            continue
        score = float(np.dot(emb, ref))
        if score > best_score:
            best_score = score
            best_name = e["name"]
            best_cat = e.get("category", "known")
    if best_score < threshold:
        # assign stable-ish unknown id from embedding hash
        uid = abs(hash(emb.tobytes())) % 1000
        return FaceMatch(name=f"Unknown Person #{uid}", category="unknown", confidence=max(0.0, best_score), bbox=(0, 0, 0, 0))
    return FaceMatch(name=best_name, category=best_cat, confidence=best_score, bbox=(0, 0, 0, 0))


def recognize_in_frame(
    frame: np.ndarray,
    person_detections: list,
) -> list[FaceMatch]:
    """Run face recognition for person detections (objects with .label and .bbox xyxy norm)."""
    results: list[FaceMatch] = []
    h, w = frame.shape[:2]
    for d in person_detections:
        label = d.label if hasattr(d, "label") else d.get("label")
        if label != "person":
            continue
        bbox = d.bbox if hasattr(d, "bbox") else d.get("bbox")
        if isinstance(bbox, dict):
            bbox = (bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"])
        faces = detect_faces_in_frame(frame, bbox)
        if not faces:
            continue
        x1, y1, x2, y2 = faces[0]["px"]
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            continue
        m = match_face(crop)
        m.bbox = (x1 / w, y1 / h, x2 / w, y2 / h)
        results.append(m)
    return results


def seed_demo_faces():
    """Create placeholder known/blacklist entries with synthetic face images."""
    if os.getenv("SKIP_VIDEO_GEN", "").lower() in ("1", "true", "yes"):
        return
    if _load_index():
        return
    for name, cat, color in [
        ("Raj (Employee)", "known", (80, 180, 120)),
        ("Priya (Staff)", "known", (180, 120, 80)),
        ("Unauthorized Suspect", "blacklist", (60, 60, 200)),
    ]:
        img = np.zeros((160, 160, 3), dtype=np.uint8)
        img[:] = color
        cv2.circle(img, (80, 70), 35, (220, 220, 220), -1)
        cv2.ellipse(img, (80, 150), (50, 40), 0, 0, 360, (200, 200, 200), -1)
        cv2.putText(img, name.split()[0][:6], (20, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        ok, buf = cv2.imencode(".jpg", img)
        if ok:
            try:
                enroll_face(name, cat, buf.tobytes())
            except Exception:
                pass
