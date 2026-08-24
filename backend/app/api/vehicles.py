"""Vehicle endpoints: detected vehicles with thumbnails and event counts."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.utils import media_url
from app.database import get_db
from app.models import Event, Vehicle
from app.schemas import VehicleOut

router = APIRouter(prefix="/api/vehicles", tags=["vehicles"])


def _to_out(v: Vehicle, counts: dict[int, int], last_types: dict[int, str | None]) -> VehicleOut:
    return VehicleOut(
        id=v.id,
        video_id=v.video_id,
        first_seen=v.first_seen,
        last_seen=v.last_seen,
        vehicle_type=v.vehicle_type,
        color=v.color,
        make_model=v.make_model,
        license_plate=v.license_plate,
        thumbnail_url=media_url(v.thumbnail_path),
        event_count=counts.get(v.id, 0),
        last_event_type=last_types.get(v.id),
    )


@router.get("", response_model=dict)
async def list_vehicles(
    video_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Vehicle)
    if video_id is not None:
        stmt = stmt.where(Vehicle.video_id == video_id)

    # Get total count
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    total_pages = max(1, (total + limit - 1) // limit)

    stmt = stmt.order_by(Vehicle.id.asc()).offset((page - 1) * limit).limit(limit)
    vehicles = list(db.scalars(stmt))

    counts = dict(
        db.execute(
            select(Event.vehicle_id, func.count(Event.id)).group_by(Event.vehicle_id)
        ).all()
    )
    last_types = dict(
        db.execute(
            select(Event.vehicle_id, func.max(Event.timestamp)).group_by(Event.vehicle_id)
        ).all()
    )
    last_type_map: dict[int, str | None] = {}
    if last_types:
        for vid, ts in last_types.items():
            last_type_map[vid] = db.scalar(
                select(Event.event_type).where(
                    Event.vehicle_id == vid, Event.timestamp == ts
                ).limit(1)
            )

    return {
        "items": [_to_out(v, counts, last_type_map) for v in vehicles],
        "total_pages": total_pages,
        "total": total,
    }


@router.get("/{vehicle_id}", response_model=VehicleOut)
async def get_vehicle(vehicle_id: int, db: Session = Depends(get_db)) -> VehicleOut:
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    count = db.scalar(select(func.count(Event.id)).where(Event.vehicle_id == vehicle_id)) or 0
    return _to_out(vehicle, {vehicle_id: count}, {})


@router.get("/{vehicle_id}/events", response_model=list)
async def get_vehicle_events(
    vehicle_id: int,
    db: Session = Depends(get_db),
) -> list:
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    events = db.execute(
        select(Event)
        .where(Event.vehicle_id == vehicle_id)
        .order_by(Event.timestamp.asc())
    ).scalars().all()

    return [
        {
            "id": e.id,
            "video_id": e.video_id,
            "person_id": e.person_id,
            "vehicle_id": e.vehicle_id,
            "timestamp": e.timestamp,
            "event_type": e.event_type,
            "description": e.description,
            "confidence": e.confidence,
            "image_url": media_url(e.image_path) if e.image_path else None,
            "thumbnail_url": media_url(e.thumbnail_path) if e.thumbnail_path else None,
            "objects": e.objects or [],
            "activity": e.activity,
            "tags": e.tags or [],
            "note": e.note,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]