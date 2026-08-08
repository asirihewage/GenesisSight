"""Shared serialization helpers for API responses."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Event, Video
from app.schemas import EventOut, StatusResponse


def media_url(rel_path: str | None) -> str | None:
    if not rel_path:
        return None
    return f"/media/{rel_path}"


def serialize_event(db: Session, event_id: int) -> EventOut | None:
    event = db.get(Event, event_id)
    if event is None:
        return None
    objects = event.objects if isinstance(event.objects, list) else []
    return EventOut(
        id=event.id,
        video_id=event.video_id,
        person_id=event.person_id,
        timestamp=event.timestamp,
        event_type=event.event_type,
        description=event.description,
        confidence=event.confidence,
        image_url=media_url(event.image_path),
        thumbnail_url=media_url(event.thumbnail_path),
        objects=[str(o) for o in objects],
        activity=event.activity,
        created_at=event.created_at,
    )


def serialize_events(db: Session, events: list[Event]) -> list[EventOut]:
    return [
        EventOut(
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
            created_at=e.created_at,
        )
        for e in events
    ]


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
