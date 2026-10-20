"""Shared catalog helpers: per-user tour status and like counts, computed in a
fixed number of queries no matter how many tours are listed."""
from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Purchase, Tour, TourLike, TourRating, TourSession, User
from app.schemas.tour import TourListItem


async def rating_stats(db: AsyncSession, tour_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, tuple[float, int]]:
    """{tour_id: (average rounded to 1 decimal, number of ratings)}."""
    if not tour_ids:
        return {}
    rows = await db.execute(
        select(TourRating.tour_id, func.avg(TourRating.rating), func.count(TourRating.user_id))
        .where(TourRating.tour_id.in_(tour_ids))
        .group_by(TourRating.tour_id)
    )
    return {r[0]: (round(float(r[1]), 1), r[2]) for r in rows.all()}


def status_for(tour: Tour, *, owned: bool, latest_session: TourSession | None, signed_in: bool) -> str:
    """not_purchased | purchased | in_progress | completed_locked (Feature Spec 1)."""
    if not tour.is_free and not (signed_in and owned):
        return "not_purchased"
    if latest_session is None:
        return "purchased"
    return "completed_locked" if latest_session.completed else "in_progress"


async def to_list_items(db: AsyncSession, user: User | None, tours: Sequence[Tour]) -> list[TourListItem]:
    if not tours:
        return []
    ids = [t.id for t in tours]

    likes = {
        row[0]: row[1]
        for row in (
            await db.execute(
                select(TourLike.tour_id, func.count(TourLike.user_id))
                .where(TourLike.tour_id.in_(ids))
                .group_by(TourLike.tour_id)
            )
        ).all()
    }

    ratings = await rating_stats(db, ids)

    owned: set[uuid.UUID] = set()
    latest: dict[uuid.UUID, TourSession] = {}
    if user is not None:
        owned = set(
            (
                await db.execute(
                    select(Purchase.tour_id).where(
                        Purchase.user_id == user.id, Purchase.tour_id.in_(ids), Purchase.status == "completed"
                    )
                )
            ).scalars()
        )
        for sess in (
            await db.execute(
                select(TourSession)
                .where(TourSession.user_id == user.id, TourSession.tour_id.in_(ids))
                .order_by(TourSession.started_at.desc())
            )
        ).scalars():
            latest.setdefault(sess.tour_id, sess)

    items = []
    for tour in tours:
        item = TourListItem.model_validate(tour)
        item.status = status_for(
            tour, owned=tour.id in owned, latest_session=latest.get(tour.id), signed_in=user is not None
        )
        item.like_count = likes.get(tour.id, 0)
        item.avg_rating, item.rating_count = ratings.get(tour.id, (None, 0))
        items.append(item)
    return items
