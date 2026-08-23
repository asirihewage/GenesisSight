"""Person endpoints: detected people with thumbnails and event counts."""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.utils import media_url
from app.database import get_db
from app.models import Event, Person
from app.schemas import PersonOut, PersonPatch, SimilarPersonOut

router = APIRouter(prefix="/api/persons", tags=["persons"])


def _to_out(p: Person, counts: dict[int, int], last_types: dict[int, str | None]) -> PersonOut:
    return PersonOut(
        id=p.id,
        video_id=p.video_id,
        first_seen=p.first_seen,
        last_seen=p.last_seen,
        name=p.name,
        thumbnail_url=media_url(p.thumbnail_path),
        event_count=counts.get(p.id, 0),
        last_event_type=last_types.get(p.id),
    )


@router.get("", response_model=list[PersonOut])
async def list_persons(
    video_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[PersonOut]:
    stmt = select(Person)
    if video_id is not None:
        stmt = stmt.where(Person.video_id == video_id)
    stmt = stmt.order_by(Person.id.asc())
    persons = list(db.scalars(stmt))

    counts = dict(
        db.execute(
            select(Event.person_id, func.count(Event.id)).group_by(Event.person_id)
        ).all()
    )
    last_types = dict(
        db.execute(
            select(Event.person_id, func.max(Event.timestamp)).group_by(Event.person_id)
        ).all()
    )
    last_type_map: dict[int, str | None] = {}
    if last_types:
        for pid, ts in last_types.items():
            last_type_map[pid] = db.scalar(
                select(Event.event_type).where(
                    Event.person_id == pid, Event.timestamp == ts
                ).limit(1)
            )

    return [_to_out(p, counts, last_type_map) for p in persons]


@router.get("/{person_id}", response_model=PersonOut)
async def get_person(person_id: int, db: Session = Depends(get_db)) -> PersonOut:
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    count = db.scalar(select(func.count(Event.id)).where(Event.person_id == person_id)) or 0
    return _to_out(person, {person_id: count}, {})


@router.patch("/{person_id}", response_model=PersonOut)
async def patch_person(
    person_id: int,
    patch: PersonPatch,
    db: Session = Depends(get_db),
) -> PersonOut:
    """Set a person's name (tag). Empty string clears it."""
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    person.name = (patch.name or "").strip() or None
    db.commit()
    db.refresh(person)
    count = db.scalar(select(func.count(Event.id)).where(Event.person_id == person_id)) or 0
    return _to_out(person, {person_id: count}, {})


@router.get("/{person_id}/similar", response_model=list[SimilarPersonOut])
async def similar_persons(
    person_id: int,
    threshold: float = Query(default=0.7, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[SimilarPersonOut]:
    """People whose ReID embedding matches this person's (cosine similarity)."""
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    if not person.embedding:
        return []
    q = np.asarray(person.embedding, dtype=np.float32)
    q_norm = float(np.linalg.norm(q)) or 1.0
    q = q / q_norm

    others = db.scalars(
        select(Person).where(Person.id != person_id, Person.embedding.is_not(None))
    ).all()

    counts = dict(
        db.execute(
            select(Event.person_id, func.count(Event.id)).group_by(Event.person_id)
        ).all()
    )

    scored: list[tuple[float, Person]] = []
    for o in others:
        vec = np.asarray(o.embedding, dtype=np.float32)
        norm = float(np.linalg.norm(vec))
        if norm <= 0:
            continue
        score = float((vec / norm) @ q)
        if score >= threshold:
            scored.append((score, o))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        SimilarPersonOut(person=_to_out(o, counts, {}), score=round(s, 4))
        for s, o in scored[:limit]
    ]
