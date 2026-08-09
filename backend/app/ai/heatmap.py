"""Per-camera activity heatmap accumulator."""

from __future__ import annotations

import threading
from typing import Optional

import cv2
import numpy as np

_lock = threading.Lock()
# camera_id -> float32 grid (H, W)
_maps: dict[int, np.ndarray] = {}
GRID = 64


def add_points(camera_id: int, points: list[tuple[float, float]], weight: float = 1.0):
    """Add normalized (x,y) detection centers to heatmap."""
    with _lock:
        if camera_id not in _maps:
            _maps[camera_id] = np.zeros((GRID, GRID), dtype=np.float32)
        m = _maps[camera_id]
        for x, y in points:
            ix = int(min(GRID - 1, max(0, x * GRID)))
            iy = int(min(GRID - 1, max(0, y * GRID)))
            m[iy, ix] += weight
            # soft blur neighbors
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = iy + dy, ix + dx
                    if 0 <= ny < GRID and 0 <= nx < GRID:
                        m[ny, nx] += weight * 0.25


def get_heatmap_array(camera_id: int) -> Optional[np.ndarray]:
    with _lock:
        m = _maps.get(camera_id)
        return None if m is None else m.copy()


def render_heatmap_png(camera_id: int, width: int = 640, height: int = 360) -> Optional[bytes]:
    m = get_heatmap_array(camera_id)
    if m is None or m.max() <= 0:
        blank = np.zeros((height, width, 3), dtype=np.uint8)
        blank[:] = (15, 20, 28)
        ok, buf = cv2.imencode(".png", blank)
        return buf.tobytes() if ok else None
    norm = m / (m.max() + 1e-6)
    heat = cv2.resize(norm, (width, height), interpolation=cv2.INTER_CUBIC)
    heat_u8 = (np.clip(heat, 0, 1) * 255).astype(np.uint8)
    colored = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)
    # darken low values for nicer overlay look
    mask = heat_u8.astype(np.float32) / 255.0
    bg = np.zeros_like(colored)
    bg[:] = (15, 20, 28)
    out = (colored.astype(np.float32) * mask[..., None] + bg.astype(np.float32) * (1 - mask[..., None])).astype(np.uint8)
    ok, buf = cv2.imencode(".png", out)
    return buf.tobytes() if ok else None


def reset(camera_id: int | None = None):
    with _lock:
        if camera_id is None:
            _maps.clear()
        else:
            _maps.pop(camera_id, None)
