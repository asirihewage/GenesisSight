"""Video upload / analysis / status / events / deletion endpoints."""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.utils import serialize_event, serialize_events, status_response, video_url
from app.config import settings
from app.core.worker import worker
from app.database import get_db
from app.models import Event, Person, Video
from app.schemas import EventOut, EventPatch, StatusResponse, UploadResponse, VideoOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/videos", tags=["videos"])

MAX_UPLOAD_BYTES = settings.max_upload_mb * 1024 * 1024


@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_video(file: UploadFile = File(...), db: Session = Depends(get_db)) -> UploadResponse:
    filename = Path(file.filename or "video.mp4").name
    ext = Path(filename).suffix.lower()
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(settings.allowed_extensions)}",
        )

    uploads_dir = Path(settings.storage_dir) / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    dest = uploads_dir / f"{uuid.uuid4().hex}_{filename}"

    written = 0
    try:
        with open(dest, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="File exceeds upload size limit")
                out.write(chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    except Exception as exc:
        dest.unlink(missing_ok=True)
        logger.exception("Upload failed")
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc

    video = Video(filename=filename, filepath=str(dest), status="uploaded")
    db.add(video)
    db.commit()
    db.refresh(video)
    logger.info("Uploaded video id=%s filename=%s", video.id, filename)
    return UploadResponse(id=video.id, filename=filename, status=video.status)


@router.post("/{video_id}/analyze", response_model=StatusResponse)
async def analyze_video(video_id: int, db: Session = Depends(get_db)) -> StatusResponse:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.status in ("queued", "processing"):
        raise HTTPException(status_code=409, detail=f"Video already {video.status}")
    video.status = "queued"
    db.commit()
    worker.enqueue(video_id)
    logger.info("Enqueued analysis for video id=%s", video_id)
    return status_response(video)


@router.get("/{video_id}/status", response_model=StatusResponse)
async def get_status(video_id: int, db: Session = Depends(get_db)) -> StatusResponse:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    pos = None
    if video.status == "queued":
        pos = worker.queued_position(video_id)
    return status_response(video, queued_position=pos)


@router.get("", response_model=list[VideoOut])
async def list_videos(
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="completed", regex="^(completed|processing|newest)$"),
) -> list[VideoOut]:
    # Sort: completed/processing first, then by creation date desc
    if sort_by == "processing":
        query = select(Video).order_by(
            Video.status != "processing",  # processing goes first (False=0, True=1)
            Video.created_at.desc()
        )
    elif sort_by == "newest":
        query = select(Video).order_by(
            Video.created_at.desc()
        )
    else:  # completed
        query = select(Video).order_by(
            Video.status != "completed",  # completed=true goes first (False=0, True=1, so !completed puts completed first)
            Video.created_at.desc()
        )
    videos = db.scalars(query.offset(offset).limit(limit)).all()
    out = [VideoOut.model_validate(v) for v in videos]
    for v, o in zip(videos, out):
        o.video_url = video_url(v)
    return out


@router.get("/{video_id}", response_model=VideoOut)
async def get_video(video_id: int, db: Session = Depends(get_db)) -> VideoOut:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    out = VideoOut.model_validate(video)
    out.video_url = video_url(video)
    return out


@router.get("/{video_id}/events", response_model=list[EventOut])
async def list_events(
    video_id: int,
    person_id: int | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[EventOut]:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    stmt = select(Event).where(Event.video_id == video_id)
    if person_id is not None:
        stmt = stmt.where(Event.person_id == person_id)
    if event_type:
        stmt = stmt.where(Event.event_type == event_type)
    stmt = stmt.order_by(Event.timestamp.asc()).offset(offset).limit(limit)
    return serialize_events(db, list(db.scalars(stmt)))


@router.patch("/{video_id}/events/{event_id}", response_model=EventOut)
async def patch_event(
    video_id: int,
    event_id: int,
    patch: EventPatch,
    db: Session = Depends(get_db),
) -> EventOut:
    """Add/update user tags and notes on an event (fed back into search)."""
    event = db.get(Event, event_id)
    if event is None or event.video_id != video_id:
        raise HTTPException(status_code=404, detail="Event not found")

    if patch.tags is not None:
        event.tags = [t.strip() for t in patch.tags if t and t.strip()]
    elif patch.tag is not None:
        tag = patch.tag.strip()
        current = list(event.tags or [])
        if tag:
            if tag not in current:
                current.append(tag)
        else:
            current = []
        event.tags = current
    if patch.note is not None:
        event.note = patch.note.strip() or None
    if event.embedding is not None:
        # annotations change search semantics — invalidate the stale cache
        event.embedding = None
    db.commit()
    db.refresh(event)
    return serialize_event(db, event.id)  # type: ignore[return-value]


@router.delete("/{video_id}")
async def delete_video(video_id: int, db: Session = Depends(get_db)) -> dict:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.status in ("queued", "processing"):
        raise HTTPException(status_code=409, detail="Cannot delete a video that is processing")
    # Delete video file
    filepath = Path(video.filepath)
    filepath.unlink(missing_ok=True)
    # Delete associated media: frames and images per video
    for sub in ("frames", "images"):
        shutil.rmtree(Path(settings.storage_dir) / sub / str(video_id), ignore_errors=True)
    # SQLAlchemy relationships cascade delete-orphan: events & persons rows removed auto
    db.delete(video)
    db.commit()
    # Return acknowledgement
    return {"ok": True, "id": video_id, "message": "Video and related data deleted successfully"}


# -- directory watching ---------------------------------------------------
WATCHED_EXTENSIONS = {".avi", ".mp4", ".mkv", ".mov", ".m4v"}


@router.get("/watch-dir", response_model=dict)
async def get_watch_dir() -> dict:
    """Get the current default watch directory setting."""
    return {
        "default_watch_dir": settings.default_watch_dir,
        "auto_scan_new_videos": settings.auto_scan_new_videos,
    }


@router.post("/watch-dir", response_model=dict)
async def set_watch_dir(dir_path: str) -> dict:
    """Set the default watch directory. Empty string disables watching."""
    settings.default_watch_dir = dir_path.strip() if dir_path else ""
    # Reload settings to pick up the new value
    get_settings.cache_clear()
    settings = get_settings()
    return {
        "default_watch_dir": settings.default_watch_dir,
        "auto_scan_new_videos": settings.auto_scan_new_videos,
        "message": f"Watch directory set to: {settings.default_watch_dir or 'disabled'}",
    }


@router.post("/watch-dir/scan", response_model=dict)
async def scan_watch_dir(db: Session = Depends(get_db)) -> dict:
    """Manually trigger a scan of the watch directory for new videos."""
    watch_dir = Path(settings.default_watch_dir) if settings.default_watch_dir else Path(settings.storage_dir)
    if not watch_dir.exists():
        return {"found": 0, "added": 0, "message": "Watch directory does not exist"}

    added = 0
    # Find all supported video files in the watch directory (recursive)
    for video_file in watch_dir.rglob("*"):
        if video_file.suffix.lower() not in WATCHED_EXTENSIONS:
            continue
        # Check if already in database
        existing = db.scalar(select(Video).where(Video.filename == video_file.name))
        if existing:
            continue
        # Create new video entry
        rel = video_file.relative_to(watch_dir.parent)
        dest = Path(settings.storage_dir) / "uploads" / f"{uuid.uuid4().hex}_{video_file.name}"
        # Move/copy file to uploads directory
        import shutil
        shutil.copy2(str(video_file), str(dest))
        video = Video(
            filename=video_file.name,
            filepath=str(dest),
            status="uploaded",
        )
        db.add(video)
        db.commit()
        db.refresh(video)
        # Enqueue for analysis if auto-scan is enabled
        if settings.auto_scan_new_videos:
            worker.enqueue(video.id)
        added += 1

    return {
        "watch_dir": str(watch_dir),
        "found": added,
        "added": added,
        "message": f"Found {added} new video(s) in watch directory",
    }


@router.post("/watch-dir/autoscan", response_model=dict)
async def set_auto_scan_toggle(enabled: bool) -> dict:
    """Enable or disable auto-scan for new videos in the watch directory."""
    settings.auto_scan_new_videos = enabled
    # Reload settings to pick up the new value
    get_settings.cache_clear()
    settings = get_settings()
    return {
        "auto_scan_new_videos": settings.auto_scan_new_videos,
        "message": f"Auto-scan {'enabled' if enabled else 'disabled'}",
    }


# -- general settings ---------------------------------------------------

@router.get("/settings", response_model=dict)
async def get_settings() -> dict:
    """Get all configurable settings."""
    return {
        "default_watch_dir": settings.default_watch_dir,
        "auto_scan_new_videos": settings.auto_scan_new_videos,
        "detect_people": settings.detect_people,
        "detect_vehicles": settings.detect_vehicles,
        "detect_animals": settings.detect_animals,
        "language": settings.language,
        "auto_scan_schedule": settings.auto_scan_schedule,
        "auto_scan_enabled": settings.auto_scan_enabled,
    }


@router.post("/settings/detection", response_model=dict)
async def set_detection_preferences(
    detect_people: bool | None = None,
    detect_vehicles: bool | None = None,
    detect_animals: bool | None = None,
) -> dict:
    """Update detection preferences."""
    if detect_people is not None:
        settings.detect_people = detect_people
    if detect_vehicles is not None:
        settings.detect_vehicles = detect_vehicles
    if detect_animals is not None:
        settings.detect_animals = detect_animals
    get_settings.cache_clear()
    settings = get_settings()
    return {
        "detect_people": settings.detect_people,
        "detect_vehicles": settings.detect_vehicles,
        "detect_animals": settings.detect_animals,
    }


@router.post("/settings/language", response_model=dict)
async def set_language(language: str) -> dict:
    """Set the UI language."""
    settings.language = language
    get_settings.cache_clear()
    settings = get_settings()
    return {"language": settings.language}


@router.post("/settings/scheduler", response_model=dict)
async def set_scheduler(
    auto_scan_schedule: str | None = None,
    auto_scan_enabled: bool | None = None,
) -> dict:
    """Update auto-scan scheduler settings."""
    if auto_scan_schedule is not None:
        settings.auto_scan_schedule = auto_scan_schedule
    if auto_scan_enabled is not None:
        settings.auto_scan_enabled = auto_scan_enabled
    get_settings.cache_clear()
    settings = get_settings()
    return {
        "auto_scan_schedule": settings.auto_scan_schedule,
        "auto_scan_enabled": settings.auto_scan_enabled,
    }


@router.get("/{video_id}/stats")
async def video_stats(video_id: int, db: Session = Depends(get_db)) -> dict:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    events = db.scalar(select(func.count(Event.id)).where(Event.video_id == video_id)) or 0
    persons = db.scalar(select(func.count(Person.id)).where(Person.video_id == video_id)) or 0
    types = dict(
        db.execute(
            select(Event.event_type, func.count(Event.id))
            .where(Event.video_id == video_id)
            .group_by(Event.event_type)
        ).all()
    )
    return {"events": events, "persons": persons, "event_types": types}
