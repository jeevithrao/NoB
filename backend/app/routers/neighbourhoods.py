"""Neighbourhoods: the "By neighbourhood" row, neighbourhood pages and the
areas a walker can collect passport stamps for."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_optional
from app.models import Neighbourhood, Tour, User
from app.schemas.neighbourhood import NeighbourhoodDetail, NeighbourhoodOut
from app.services.catalog import to_list_items

router = APIRouter(prefix="/neighbourhoods", tags=["neighbourhoods"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": "NEIGHBOURHOOD_NOT_FOUND", "message": "Neighbourhood not found."}},
    )


async def _tour_counts(db: AsyncSession) -> dict[uuid.UUID, int]:
    rows = await db.execute(
        select(Tour.neighbourhood_id, func.count(Tour.id))
        .where(Tour.is_published.is_(True), Tour.neighbourhood_id.is_not(None))
        .group_by(Tour.neighbourhood_id)
    )
    return {r[0]: r[1] for r in rows.all()}


@router.get("", response_model=list[NeighbourhoodOut])
async def list_neighbourhoods(
    city: str = Query(default="Bangalore"),
    include_empty: bool = Query(default=False, description="Also return areas with no published tour yet"),
    db: AsyncSession = Depends(get_db),
):
    hoods = (
        await db.execute(select(Neighbourhood).where(Neighbourhood.city == city).order_by(Neighbourhood.name))
    ).scalars().all()
    counts = await _tour_counts(db)
    out = []
    for hood in hoods:
        item = NeighbourhoodOut.model_validate(hood)
        item.tour_count = counts.get(hood.id, 0)
        if item.tour_count or include_empty:
            out.append(item)
    return out


@router.get("/{id_or_slug}", response_model=NeighbourhoodDetail)
async def get_neighbourhood(
    id_or_slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    try:
        condition = Neighbourhood.id == uuid.UUID(id_or_slug)
    except ValueError:
        condition = Neighbourhood.slug == id_or_slug
    hood = (await db.execute(select(Neighbourhood).where(condition))).scalar_one_or_none()
    if hood is None:
        raise _not_found()

    tours = (
        await db.execute(
            select(Tour)
            .where(Tour.neighbourhood_id == hood.id, Tour.is_published.is_(True))
            .order_by(Tour.created_at.desc(), Tour.id)
        )
    ).scalars().unique().all()

    # Build from the plain columns: validating the ORM object directly would try
    # to lazy-load `hood.tours` (not allowed in async code).
    base = NeighbourhoodOut.model_validate(hood).model_dump()
    base["tour_count"] = len(tours)
    return NeighbourhoodDetail(**base, tours=await to_list_items(db, current_user, tours))
