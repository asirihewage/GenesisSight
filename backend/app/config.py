"""Application configuration.

All settings can be overridden via environment variables or a `.env` file at the
project root (see `.env.example`). Pydantic-settings loads and validates them.
Runtime settings (watch dir, detection prefs, language, scheduler) are persisted
to a JSON file in the storage directory.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root: <root>/backend/app/config.py -> parents[2]
BASE_DIR = Path(__file__).resolve().parents[2]

# Storage layouts (created on demand)
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", str(BASE_DIR / "storage")))
UPLOADS_DIR = STORAGE_DIR / "uploads"
FRAMES_DIR = STORAGE_DIR / "frames"
IMAGES_DIR = STORAGE_DIR / "images"
DATABASE_DIR = STORAGE_DIR / "database"
MODELS_DIR = Path(os.getenv("MODEL_DIR", str(BASE_DIR / "models")))

RUNTIME_SETTINGS_FILE = STORAGE_DIR / "runtime_settings.json"


def default_database_url() -> str:
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(DATABASE_DIR / 'cctv.db').as_posix()}"


def load_runtime_settings() -> dict[str, Any]:
    """Load runtime settings from JSON file."""
    if RUNTIME_SETTINGS_FILE.exists():
        try:
            return json.loads(RUNTIME_SETTINGS_FILE.read_text())
        except Exception:
            pass
    return {}


def save_runtime_settings(data: dict[str, Any]) -> None:
    """Save runtime settings to JSON file."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_SETTINGS_FILE.write_text(json.dumps(data, indent=2))


class Settings(BaseSettings):
    """Runtime settings. Env vars / .env override defaults."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- service -----------------------------------------------------------
    app_name: str = "Local AI CCTV Analyzer"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    frontend_port: int = 3000
    prod_mode: bool = False  # True => FastAPI serves built frontend on api_port
    log_level: str = "INFO"

    # -- storage / database ------------------------------------------------
    storage_dir: str = str(STORAGE_DIR)
    database_url: str = Field(default_factory=default_database_url)
    max_upload_mb: int = 2048
    allowed_extensions: list[str] = [".avi", ".mp4", ".mkv", ".mov", ".m4v"]

    # -- models ------------------------------------------------------------
    model_dir: str = str(MODELS_DIR)
    yolo_model: str = "yolo11x.pt"
    yolo_conf: float = 0.30
    yolo_iou: float = 0.50
    yolo_img_size: int = 1280
    device: str = "auto"  # auto | cuda:0 | cpu

    # ReID: "osnet" (torchreid + weights file) | "resnet" | "disabled"
    reid_engine: str = "osnet"
    reid_weights: str = ""  # path to osnet weights, e.g. models/osnet_x1_0_imagenet.pth
    reid_match_threshold: float = 0.70  # cosine similarity to merge into a person

    # -- pipeline ----------------------------------------------------------
    target_fps: float = 3.0        # processing sampling rate
    motion_threshold: float = 0.0025  # min changed-pixel ratio to run YOLO
    detect_batch_size: int = 8     # frames per YOLO forward pass
    reid_refresh_interval: int = 25  # frames between embedding refresh per track
    vlm_enabled: bool = True
    vlm_max_events: int = 40       # max events sent to the VLM per video
    vlm_confidence_min: float = 0.3  # accept VLM description above this conf

    # -- ollama ------------------------------------------------------------
    ollama_base_url: str = "http://localhost:11434"
    ollama_vlm_model: str = "qwen2.5vl:7b"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_timeout_s: int = 180
    ollama_connect_timeout_s: int = 3

    # -- LPR (License Plate Recognition) -----------------------------------
    lpr_enabled: bool = True
    lpr_model: str = "yolo11n-license-plate.pt"  # YOLO model for plate detection
    lpr_conf: float = 0.25
    lpr_ocr_lang: list[str] = ["en"]  # OCR languages for EasyOCR
    lpr_min_confidence: float = 0.5  # Minimum OCR confidence to accept plate

    # -- websocket / queue -------------------------------------------------
    ws_broadcast_enabled: bool = True

    # -- runtime settings (loaded from JSON, not env) ---------------------
    default_watch_dir: str = ""           # empty = disabled
    auto_scan_new_videos: bool = True     # auto-analyze files placed in watch dir
    detect_people: bool = True
    detect_vehicles: bool = True
    detect_animals: bool = False
    language: str = "en"
    auto_scan_schedule: str = ""
    auto_scan_enabled: bool = False

    @property
    def cuda_available(self) -> bool:
        if self.device == "cpu":
            return False
        try:
            import torch

            return torch.cuda.is_available()
        except Exception:
            return False

    @property
    def torch_device(self) -> str:
        if self.device == "cpu":
            return "cpu"
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            pass
        return "cpu"


_runtime_settings_cache: dict[str, Any] = {}


@lru_cache
def get_settings() -> Settings:
    # Load base settings from env/.env
    base = Settings()
    # Override with persisted runtime settings
    runtime = load_runtime_settings()
    for key, value in runtime.items():
        if hasattr(base, key):
            setattr(base, key, value)
    return base


def update_runtime_setting(key: str, value: Any) -> None:
    """Update a single runtime setting and persist to JSON."""
    global _runtime_settings_cache
    runtime = load_runtime_settings()
    runtime[key] = value
    save_runtime_settings(runtime)
    # Clear cache so next get_settings() picks up the change
    get_settings.cache_clear()


def update_runtime_settings(updates: dict[str, Any]) -> None:
    """Update multiple runtime settings and persist to JSON."""
    global _runtime_settings_cache
    runtime = load_runtime_settings()
    runtime.update(updates)
    save_runtime_settings(runtime)
    get_settings.cache_clear()


settings = get_settings()
