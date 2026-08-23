"""Shared serialization helpers for API responses."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Event, Video
from app.schemas import EventOut, StatusResponse


def media_url(rel_path: str | None) -> str | None:
    if not rel_path:
        return None
    return f"/media/{rel_path}"


def video_url(video: Video) -> str | None:
    from app.config import settings

    try:
        rel = Path(video.filepath).resolve().relative_to(Path(settings.storage_dir).resolve())
    except (ValueError, OSError):
        return None
    return f"/media/{rel.as_posix()}"


def serialize_event(db: Session, event_id: int) -> EventOut | None:
    event = db.get(Event, event_id)
    if event is None:
        return None
    return _serialize(event)


def serialize_events(db: Session, events: list[Event]) -> list[EventOut]:
    return [_serialize(e) for e in events]


def _serialize(e: Event) -> EventOut:
    return EventOut(
        id=e.id,
        video_id=e.video_id,
        person_id=e.person_id,
        timestamp=e.timestamp,
        event_type=e.event_type,
        description=e.description,
        confidence=e.confidence,
        image_url=media_url(e.image_path),
        thumbnail_url=media_url(e.thumbnail_path),
        objects=[str(o) for o in (e.objects if isinstance(e.objects, list) else [])],
        activity=e.activity,
        tags=[str(t) for t in (e.tags if isinstance(e.tags, list) else [])],
        note=e.note,
        created_at=e.created_at,
    )


def status_response(video: Video, queued_position: int | None = None) -> StatusResponse:
    return StatusResponse(
        id=video.id,
        filename=video.filename,
        status=video.status,
        progress=video.progress,
        current_stage=video.current_stage,
        fps_processed=video.fps_processed,
        error=video.error,
        queued_position=queued_position,
    )
