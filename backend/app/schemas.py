"""Pydantic schemas for the REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------
# Videos
# --------------------------------------------------------------------------
class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    duration: float
    width: int
    height: int
    fps: float
    status: str
    progress: float
    current_stage: str
    fps_processed: float
    error: str | None = None
    created_at: datetime
    video_url: str | None = None


class UploadResponse(BaseModel):
    id: int
    filename: str
    status: str


class StatusResponse(BaseModel):
    id: int
    filename: str
    status: str
    progress: float
    current_stage: str
    fps_processed: float
    error: str | None = None
    queued_position: int | None = None


# --------------------------------------------------------------------------
# Persons
# --------------------------------------------------------------------------
class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int | None
    first_seen: float
    last_seen: float
    name: str | None = None
    thumbnail_url: str | None = None
    event_count: int = 0
    last_event_type: str | None = None


class PersonPatch(BaseModel):
    name: str | None = Field(default=None, max_length=128)


class SimilarPersonOut(BaseModel):
    person: PersonOut
    score: float


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------
class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    person_id: int | None
    timestamp: float
    event_type: str
    description: str
    confidence: float
    image_url: str | None = None
    thumbnail_url: str | None = None
    objects: list[str] = Field(default_factory=list)
    activity: str | None = None
    tags: list[str] = Field(default_factory=list)
    note: str | None = None
    created_at: datetime


class EventPatch(BaseModel):
    tags: list[str] | None = Field(default=None, max_length=20)
    tag: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=2000)


class SearchResult(BaseModel):
    event: EventOut
    score: float


class SearchResponse(BaseModel):
    query: str
    method: str
    results: list[SearchResult]


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------
class ModelHealth(BaseModel):
    name: str
    available: bool
    detail: str


class HealthOut(BaseModel):
    app: str
    version: str = "1.0.0"
    cuda_available: bool
    gpu_name: str | None
    device: str
    torch_version: str | None
    yolo: ModelHealth
    reid: ModelHealth
    ollama: ModelHealth
    ollama_models: list[str] = []
    storage_dir: str
    storage_used_mb: float
    videos: int


class WsMessage(BaseModel):
    type: str  # progress | event | status
    video_id: int
    payload: Any
