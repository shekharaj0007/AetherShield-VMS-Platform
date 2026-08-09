"""Lightweight SQLite column migrations for existing DBs."""

from sqlalchemy import text
from app.db.session import engine


def ensure_camera_columns():
    """Add is_demo / enabled if missing (SQLite)."""
    with engine.begin() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(cameras)")).fetchall()}
        if "is_demo" not in cols:
            conn.execute(text("ALTER TABLE cameras ADD COLUMN is_demo BOOLEAN DEFAULT 0"))
            # Mark existing sample-file cameras as demo
            conn.execute(
                text(
                    "UPDATE cameras SET is_demo = 1 "
                    "WHERE source_type = 'file' AND source_uri LIKE 'sample-data/%'"
                )
            )
        if "enabled" not in cols:
            conn.execute(text("ALTER TABLE cameras ADD COLUMN enabled BOOLEAN DEFAULT 1"))
