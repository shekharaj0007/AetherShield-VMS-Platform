"""Lightweight SQLite column migrations for existing DBs."""

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.session import engine


def _is_sqlite(bind: Engine) -> bool:
    return str(bind.url).startswith("sqlite")


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table},
    ).first()
    return row is not None


def _add_column(conn, table: str, column: str, ddl: str) -> None:
    if not _table_exists(conn, table):
        return
    cols = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()}
    if column not in cols:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def ensure_camera_columns(bind: Engine | None = None):
    """Add columns introduced after the first schema (SQLite)."""
    bind = bind or engine
    if not _is_sqlite(bind):
        return
    with bind.begin() as conn:
        if not _table_exists(conn, "cameras"):
            return
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(cameras)")).fetchall()}
        if "is_demo" not in cols:
            conn.execute(text("ALTER TABLE cameras ADD COLUMN is_demo BOOLEAN DEFAULT 0"))
            conn.execute(
                text(
                    "UPDATE cameras SET is_demo = 1 "
                    "WHERE source_type = 'file' AND source_uri LIKE 'sample-data/%'"
                )
            )
        if "enabled" not in cols:
            conn.execute(text("ALTER TABLE cameras ADD COLUMN enabled BOOLEAN DEFAULT 1"))
        _add_column(conn, "cameras", "site_id", "INTEGER")
        _add_column(conn, "alerts", "policy_id", "INTEGER")
        _add_column(conn, "alerts", "acknowledged", "BOOLEAN DEFAULT 0")
        _add_column(conn, "alerts", "acknowledged_by", "INTEGER")
        _add_column(conn, "alerts", "acknowledged_at", "DATETIME")
        _add_column(conn, "cameras", "last_seen_at", "DATETIME")
