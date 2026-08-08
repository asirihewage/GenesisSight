"""Database engine, session factory and declarative base.

Uses portable column types (JSON, Float, Integer, DateTime) so the same schema
works on SQLite (default) and PostgreSQL (set DATABASE_URL accordingly).
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def _connect_args() -> dict[str, Any]:
    if settings.database_url.startswith("sqlite"):
        # sqlite is single-writer: busy_timeout avoids "database is locked"
        # from the concurrent analysis worker + API threads.
        return {"check_same_thread": False, "timeout": 30}
    return {}


engine = create_engine(
    settings.database_url,
    connect_args=_connect_args(),
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create tables and ensure storage directories exist."""
    from app import models  # noqa: F401  (register tables)

    for path in (
        settings.storage_dir,
        settings.model_dir,
    ):
        import pathlib

        pathlib.Path(path).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
