"""SQLAlchemy ORM models: Video, Person, Event.

PostgreSQL compatible: uses JSON / Float / Integer / DateTime columns, explicit
indexes, and no SQLite-only types.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

VIDEO_STATUSES = ("uploaded", "queued", "processing", "completed", "failed")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    filepath: Mapped[str] = mapped_column(Text, nullable=False)
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    fps: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="uploaded", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    current_stage: Mapped[str] = mapped_column(String(256), default="")
    fps_processed: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    events: Mapped[list["Event"]] = relationship(
        back_populates="video", cascade="all, delete-orphan", passive_deletes=True
    )
    persons: Mapped[list["Person"]] = relationship(
        back_populates="video", cascade="all, delete-orphan", passive_deletes=True
    )


class Person(Base):
    __tablename__ = "persons"
    __table_args__ = (Index("ix_persons_video", "video_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int | None] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), nullable=True, index=True
    )
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # user-assigned name ("tag") for this person
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # ReID embedding (list[float]); may be None if ReID is disabled
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    first_seen: Mapped[float] = mapped_column(Float, default=0.0)
    last_seen: Mapped[float] = mapped_column(Float, default=0.0)
    thumbnail_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    video: Mapped[Video | None] = relationship(back_populates="persons")
    events: Mapped[list["Event"]] = relationship(back_populates="person")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_video_ts", "video_id", "timestamp"),
        Index("ix_events_person", "person_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[int | None] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"), nullable=True, index=True
    )
    timestamp: Mapped[float] = mapped_column(Float, default=0.0)  # seconds into the video
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    objects: Mapped[list | None] = mapped_column(JSON, nullable=True)
    activity: Mapped[str | None] = mapped_column(String(256), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # user annotations, fed back into semantic search
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)  # search cache
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    video: Mapped[Video] = relationship(back_populates="events")
    person: Mapped[Person | None] = relationship(back_populates="events")
