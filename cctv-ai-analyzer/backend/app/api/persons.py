"""Person endpoints: detected people with thumbnails and event counts."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.utils import media_url
from app.database import get_db
from app.models import Event, Person
from app.schemas import PersonOut

router = APIRouter(prefix="/api/persons", tags=["persons"])


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

    out: list[PersonOut] = []
    for p in persons:
        out.append(
            PersonOut(
                id=p.id,
                video_id=p.video_id,
                first_seen=p.first_seen,
                last_seen=p.last_seen,
                thumbnail_url=media_url(p.thumbnail_path),
                event_count=counts.get(p.id, 0),
                last_event_type=last_type_map.get(p.id),
            )
        )
    return out


@router.get("/{person_id}", response_model=PersonOut)
async def get_person(person_id: int, db: Session = Depends(get_db)) -> PersonOut:
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    count = db.scalar(select(func.count(Event.id)).where(Event.person_id == person_id)) or 0
    return PersonOut(
        id=person.id,
        video_id=person.video_id,
        first_seen=person.first_seen,
        last_seen=person.last_seen,
        thumbnail_url=media_url(person.thumbnail_path),
        event_count=count,
    )
