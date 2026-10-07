"""Application settings (pydantic-settings). Values come from the environment, then <root>/.env.

Settings are read at call time through ``get_settings()`` so tests can override them.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ALLOWED_MIME = (
    "video/mp4,video/webm,video/quicktime,"
    "image/jpeg,image/png,image/webp,"
    "audio/webm,audio/ogg,audio/mpeg,audio/wav,audio/mp4,"
    "application/pdf"
)

APP_VERSION = "0.1.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), env_file_encoding="utf-8", extra="ignore")

    KP_MODE: Literal["demo", "real"] = "demo"
    DATABASE_URL: str = f"sqlite:///{(ROOT / 'database' / 'kp.db').as_posix()}"
    JWT_SECRET: str = "dev-only-insecure-secret-change-me"
    JWT_EXPIRE_MINUTES: int = 480
    STORAGE_DIR: Path = ROOT / "storage"
    DEMO_ASSET_PATH: Path = ROOT / "storage" / "demo" / "practical_demo.mp4"
    MAX_UPLOAD_MB: float = 300
    ALLOWED_MIME_TYPES: str = DEFAULT_ALLOWED_MIME
    KAPPA_MIN_PAIRS: int = 30
    METRIC_MIN_N: int = 10
    MEDIA_TOKEN_TTL_S: int = 900

    # Optional AI providers. Empty key => adapter reports "unavailable"; nothing is faked.
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    LLM_PROVIDER: Literal["auto", "claude", "gemini", "none"] = "auto"
    CLAUDE_MODEL: str = "claude-sonnet-5-5"
    GEMINI_MODEL: str = "gemini-2.5-flash"
    ASR_PROVIDER: Literal["none", "faster_whisper"] = "none"
    ASR_MODEL: str = "small"
    OCR_PROVIDER: Literal["auto", "tesseract", "none"] = "auto"
    SCENE_THRESHOLD: float = 0.15
    FALLBACK_WINDOW_S: float = 30.0

    FRONTEND_DIST: Path = ROOT / "frontend" / "out"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def allowed_mime_types(self) -> set[str]:
        return {m.strip().lower() for m in self.ALLOWED_MIME_TYPES.split(",") if m.strip()}

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return int(self.MAX_UPLOAD_MB * 1024 * 1024)

    @property
    def uploads_dir(self) -> Path:
        return Path(self.STORAGE_DIR) / "uploads"

    @property
    def tmp_dir(self) -> Path:
        return Path(self.STORAGE_DIR) / "tmp"

    @property
    def is_demo_mode(self) -> bool:
        return self.KP_MODE == "demo"


@lru_cache
def get_settings() -> Settings:
    return Settings()
