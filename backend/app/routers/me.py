"""The signed-in user's own aggregates: profile stats and passport stamps."""
import uuid
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Neighbourhood, Tour, TourSession, User
from app.schemas.me import Passport, PassportStamp, ProfileStats
from app.schemas.tour import NeighbourhoodRef

router = APIRouter(prefix="/me", tags=["me"])


async def _completed_walks(db: AsyncSession, user: User):
    """One row per finished walk (the DB guarantees at most one per user+tour)."""
    return (
        await db.execute(
            select(
                TourSession.tour_id,
                TourSession.stops_visited,
                TourSession.completed_at,
                Tour.distance_km,
                Tour.duration_min,
                Tour.neighbourhood_id,
            )
            .join(Tour, Tour.id == TourSession.tour_id)
            .where(TourSession.user_id == user.id, TourSession.completed.is_(True))
        )
    ).all()


@router.get("/stats", response_model=ProfileStats)
async def my_stats(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """The three numbers on the Profile screen (plus a couple of extras)."""
    rows = await _completed_walks(db, current_user)
    return ProfileStats(
        walks_completed=len(rows),
        distance_km=round(sum(float(r.distance_km or 0) for r in rows), 1),
        stops_visited=sum(r.stops_visited for r in rows),
        listening_minutes=sum(r.duration_min or 0 for r in rows),
        neighbourhoods_stamped=len({r.neighbourhood_id for r in rows if r.neighbourhood_id}),
    )


@router.get("/passport", response_model=Passport)
async def my_passport(
    city: str = Query(default="Bangalore"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """"My Passport": one stamp slot per neighbourhood that has a published
    tour. A stamp is earned by completing any walk in that neighbourhood."""
    hoods = (
        await db.execute(select(Neighbourhood).where(Neighbourhood.city == city).order_by(Neighbourhood.name))
    ).scalars().all()
    totals = {
        r[0]: r[1]
        for r in (
            await db.execute(
                select(Tour.neighbourhood_id, func.count(Tour.id))
                .where(Tour.is_published.is_(True), Tour.neighbourhood_id.is_not(None))
                .group_by(Tour.neighbourhood_id)
            )
        ).all()
    }

    completed: dict[uuid.UUID, int] = defaultdict(int)
    first_at: dict[uuid.UUID, datetime] = {}
    for row in await _completed_walks(db, current_user):
        if row.neighbourhood_id is None:
            continue
        completed[row.neighbourhood_id] += 1
        if row.completed_at and (row.neighbourhood_id not in first_at or row.completed_at < first_at[row.neighbourhood_id]):
            first_at[row.neighbourhood_id] = row.completed_at

    stamps = []
    for hood in hoods:
        if not totals.get(hood.id) and not completed.get(hood.id):
            continue  # nothing to collect there yet
        stamps.append(
            PassportStamp(
                neighbourhood=NeighbourhoodRef.model_validate(hood),
                cover_image=hood.cover_image,
                tours_total=totals.get(hood.id, 0),
                tours_completed=completed.get(hood.id, 0),
                stamped=completed.get(hood.id, 0) > 0,
                stamped_at=first_at.get(hood.id),
            )
        )
    stamps.sort(key=lambda s: (not s.stamped, s.stamped_at or datetime.max.replace(tzinfo=None), s.neighbourhood.name))
    return Passport(
        stamps_collected=sum(s.stamped for s in stamps), total_neighbourhoods=len(stamps), stamps=stamps
    )
