"""Natural language event search."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import SearchResponse
from app.services.embeddings import search_service

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search_events(
    q: str = Query(..., min_length=1, max_length=300),
    video_id: int | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> SearchResponse:
    results, method = await search_service.search(db, q, video_id=video_id, limit=limit)
    return SearchResponse(
        query=q,
        method=method,
        results=[{"event": ev, "score": score} for ev, score in results],
    )
