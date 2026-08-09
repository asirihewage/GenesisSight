"""Health / environment info used by the Settings page."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Video
from app.schemas import HealthOut, ModelHealth
from app.services.ollama import ollama_client

router = APIRouter(prefix="/api/health", tags=["health"])


def _model_health(name: str, available: bool, detail: str) -> ModelHealth:
    return ModelHealth(name=name, available=available, detail=detail)


@router.get("", response_model=HealthOut)
async def health(db: Session = Depends(get_db)) -> HealthOut:
    # GPU / torch
    cuda = False
    gpu_name: str | None = None
    torch_version: str | None = None
    try:
        import torch

        torch_version = torch.__version__
        cuda = torch.cuda.is_available()
        if cuda:
            gpu_name = torch.cuda.get_device_name(0)
    except Exception:
        pass

    # YOLO
    yolo_available = False
    yolo_detail = "not loaded"
    try:
        yolo_path = Path(settings.model_dir) / settings.yolo_model
        yolo_available = yolo_path.exists()
        yolo_detail = f"{settings.yolo_model} ({'weights found' if yolo_available else 'will auto-download on first analysis'})"
    except Exception as exc:
        yolo_detail = str(exc)

    # ReID
    reid_backend = "not initialized"
    try:
        from app.services.reid import get_reid_engine

        reid = get_reid_engine()
        reid_backend = f"backend={reid.backend}, dim={reid.dim}"
    except Exception as exc:
        reid_backend = f"error: {exc}"

    # Ollama
    ollama_ok = ollama_client.is_available_sync()
    models = ollama_client.list_models_sync() if ollama_ok else []

    storage = Path(settings.storage_dir)
    used_mb = sum(
        f.stat().st_size for f in storage.rglob("*") if f.is_file()
    ) / (1024 * 1024) if storage.exists() else 0.0

    video_count = db.scalar(select(func.count(Video.id))) or 0

    return HealthOut(
        app=settings.app_name,
        cuda_available=cuda,
        gpu_name=gpu_name,
        device=settings.torch_device,
        torch_version=torch_version,
        yolo=_model_health("YOLO11x", yolo_available, yolo_detail),
        reid=_model_health("Person ReID", True, reid_backend),
        ollama=_model_health(
            "Ollama", ollama_ok,
            f"connected: {settings.ollama_base_url}" if ollama_ok
            else f"unreachable: {settings.ollama_base_url}",
        ),
        ollama_models=models,
        storage_dir=str(storage),
        storage_used_mb=round(used_mb, 1),
        videos=video_count,
    )
