"""AetherShield VMS — Enterprise AI Video Management System."""

import os
from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


def _resolve_base_dir() -> Path:
    env = os.getenv("PROJECT_ROOT")
    if env:
        return Path(env)
    # Local monorepo: backend/app/core/config.py → repo root
    candidate = Path(__file__).resolve().parents[3]
    if (candidate / "frontend").exists() or (candidate / "sample-data").exists():
        return candidate
    # Docker / flat layout: /app/app/core/config.py → /app
    return Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    APP_NAME: str = "AetherShield VMS"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    SECRET_KEY: str = "aethershield-dev-secret-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    BASE_DIR: Path = _resolve_base_dir()
    STORAGE_DIR: Path = BASE_DIR / "storage"
    RECORDINGS_DIR: Path = STORAGE_DIR / "recordings"
    SNAPSHOTS_DIR: Path = STORAGE_DIR / "snapshots"
    SAMPLE_DIR: Path = BASE_DIR / "sample-data" / "videos"
    DB_PATH: Path = BASE_DIR / "storage" / "vms.db"

    DATABASE_URL: str = ""

    # AI
    YOLO_MODEL: str = "yolo11n.pt"
    DETECTION_CONFIDENCE: float = 0.45
    DETECTION_INTERVAL_MS: int = 200
    TRACK_ENABLED: bool = True

    # Streaming
    JPEG_QUALITY: int = 75
    DEFAULT_FPS: int = 15
    RECORD_SEGMENT_SECONDS: int = 60

    # CORS — set CORS_ORIGINS as JSON list env on Render, e.g.
    # ["https://aethershield-ui.onrender.com"]
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "https://aethershield-ui.onrender.com",
        "https://aethershield-vms-platform.onrender.com",
    ]

    # LLM (optional — rule-based fallback if unset)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    class Config:
        env_file = ".env"
        extra = "ignore"

    def model_post_init(self, __context) -> None:
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"sqlite:///{self.DB_PATH.as_posix()}"
        self.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        self.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        self.SAMPLE_DIR.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
