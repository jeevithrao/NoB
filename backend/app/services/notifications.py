"""Creating in-app notifications. Every function here is idempotent (dedupe key) and
silent for users who switched notifications off. None of them commit: they join the
caller's transaction, so a notification exists if and only if the event it describes does."""
from __future__ import annotations

import uuid

from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification, Purchase, Tour, User


def format_price(paise: int) -> str:
    if paise <= 0:
        return "Free"
    rupees, rest = divmod(paise, 100)
    return f"₹{rupees}" if rest == 0 else f"₹{rupees}.{rest:02d}"


async def notify(
    db: AsyncSession,
    user_id: uuid.UUID,
    type_: str,
    title: str,
    subtitle: str | None,
    *,
    dedupe_key: str,
    tour_id: uuid.UUID | None = None,
) -> None:
    enabled = (await db.execute(select(User.notifications_enabled).where(User.id == user_id))).scalar_one_or_none()
    if not enabled:
        return
    await db.execute(
        pg_insert(Notification)
        .values(user_id=user_id, type=type_, title=title, subtitle=subtitle, tour_id=tour_id, dedupe_key=dedupe_key)
        .on_conflict_do_nothing(index_elements=["user_id", "dedupe_key"])
    )


async def purchase_confirmed(db: AsyncSession, purchase: Purchase) -> None:
    tour = await db.get(Tour, purchase.tour_id)
    await notify(
        db,
        purchase.user_id,
        "confirmed",
        "You're in!",
        f"{tour.name}: start whenever you're ready" if tour else "Start whenever you're ready",
        dedupe_key=f"confirmed:{purchase.id}",
        tour_id=purchase.tour_id,
    )


async def walk_completed(db: AsyncSession, user_id: uuid.UUID, tour: Tour, session_id: uuid.UUID) -> None:
    await notify(
        db,
        user_id,
        "review",
        "How was your walk?",
        f"Leave a review for {tour.name}",
        dedupe_key=f"review:{session_id}",
        tour_id=tour.id,
    )


async def tour_published(db: AsyncSession, tour: Tour) -> int:
    """Announce a newly published walk to every user who has notifications on.
    One INSERT ... SELECT, however many users there are."""
    parts = [tour.neighbourhood.name if tour.neighbourhood else None]
    if tour.distance_km is not None:
        parts.append(f"{float(tour.distance_km):g}km")
    parts.append(format_price(tour.price_paise))
    subtitle = " · ".join(p for p in parts if p)

    stmt = pg_insert(Notification).from_select(
        ["id", "user_id", "type", "title", "subtitle", "tour_id", "dedupe_key"],
        select(
            func.gen_random_uuid(),
            User.id,
            literal("new"),
            literal(f"New walk: {tour.name}"[:255]),
            literal(subtitle),
            literal(tour.id),
            literal(f"new:{tour.id}"),
        ).where(User.role == "user", User.deleted_at.is_(None), User.notifications_enabled.is_(True)),
    ).on_conflict_do_nothing(index_elements=["user_id", "dedupe_key"])
    result = await db.execute(stmt)
    return result.rowcount or 0
