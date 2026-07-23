import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, get_current_user_optional
from app.models import Purchase, Stop, Tour, TourLike, TourSession, User
from app.schemas.tour import StopWithAudio, TourDetail, TourListItem, TourPackage

router = APIRouter(prefix="/tours", tags=["tours"])


def _api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


async def _user_status_for_tour(db: AsyncSession, user: User | None, tour: Tour) -> str:
    """not_purchased | purchased | in_progress | completed_locked — per Feature
    Spec 1 licensing rules. Free tours skip the purchase gate but still track
    walk progress."""
    if not tour.is_free:
        if user is None:
            return "not_purchased"
        result = await db.execute(
            select(Purchase).where(
                Purchase.user_id == user.id,
                Purchase.tour_id == tour.id,
                Purchase.status == "completed",
            )
        )
        if result.scalar_one_or_none() is None:
            return "not_purchased"

    if user is None:
        return "purchased"

    session_result = await db.execute(
        select(TourSession)
        .where(TourSession.user_id == user.id, TourSession.tour_id == tour.id)
        .order_by(TourSession.started_at.desc())
    )
    session = session_result.scalars().first()
    if session is None:
        return "purchased"
    return "completed_locked" if session.completed else "in_progress"


async def _like_count(db: AsyncSession, tour_id: uuid.UUID) -> int:
    result = await db.execute(select(func.count()).select_from(TourLike).where(TourLike.tour_id == tour_id))
    return result.scalar_one()


@router.get("", response_model=list[TourListItem])
async def list_tours(
    city: str = Query(default="Bangalore"),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    result = await db.execute(
        select(Tour).where(Tour.city == city, Tour.is_published.is_(True)).order_by(Tour.created_at.desc())
    )
    tours = result.scalars().all()
    if not tours:
        return []

    tour_ids = [t.id for t in tours]

    # Batch query like counts across all returned tours (O(1) database queries)
    likes_result = await db.execute(
        select(TourLike.tour_id, func.count(TourLike.id))
        .where(TourLike.tour_id.in_(tour_ids))
        .group_by(TourLike.tour_id)
    )
    like_counts = {row[0]: row[1] for row in likes_result.all()}

    # Batch query user purchases and sessions if logged in
    purchased_tour_ids = set()
    latest_sessions = {}
    if current_user is not None:
        purchases_result = await db.execute(
            select(Purchase.tour_id).where(
                Purchase.user_id == current_user.id,
                Purchase.tour_id.in_(tour_ids),
                Purchase.status == "completed",
            )
        )
        purchased_tour_ids = set(purchases_result.scalars().all())

        sessions_result = await db.execute(
            select(TourSession)
            .where(
                TourSession.user_id == current_user.id,
                TourSession.tour_id.in_(tour_ids),
            )
            .order_by(TourSession.started_at.desc())
        )
        for sess in sessions_result.scalars().all():
            if sess.tour_id not in latest_sessions:
                latest_sessions[sess.tour_id] = sess

    items = []
    for tour in tours:
        if not tour.is_free:
            if current_user is None or tour.id not in purchased_tour_ids:
                status_ = "not_purchased"
            else:
                sess = latest_sessions.get(tour.id)
                if sess is None:
                    status_ = "purchased"
                else:
                    status_ = "completed_locked" if sess.completed else "in_progress"
        else:
            if current_user is None:
                status_ = "purchased"
            else:
                sess = latest_sessions.get(tour.id)
                if sess is None:
                    status_ = "purchased"
                else:
                    status_ = "completed_locked" if sess.completed else "in_progress"

        item = TourListItem.model_validate(tour)
        item.status = status_
        item.like_count = like_counts.get(tour.id, 0)
        items.append(item)
    return items



@router.get("/{tour_id}", response_model=TourDetail)
async def get_tour(
    tour_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    tour = await db.get(Tour, tour_id)
    if tour is None or not tour.is_published:
        raise _api_error(status.HTTP_404_NOT_FOUND, "TOUR_NOT_FOUND", "Tour not found.")

    status_ = await _user_status_for_tour(db, current_user, tour)
    like_count = await _like_count(db, tour.id)
    stop_count_result = await db.execute(select(func.count()).select_from(Stop).where(Stop.tour_id == tour.id))

    detail = TourDetail.model_validate(tour)
    detail.status = status_
    detail.like_count = like_count
    detail.stop_count = stop_count_result.scalar_one()

    if current_user is not None and not tour.is_free:
        purchase_result = await db.execute(
            select(Purchase).where(
                Purchase.user_id == current_user.id,
                Purchase.tour_id == tour.id,
                Purchase.status == "completed",
            )
        )
        purchase = purchase_result.scalar_one_or_none()
        if purchase is not None:
            detail.purchase_id = purchase.id

    return detail


@router.get("/{tour_id}/package", response_model=TourPackage)
async def get_tour_package(
    tour_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stop manifest + signed audio URLs for offline download (Feature Spec 3).
    Requires a completed purchase unless the tour is free."""
    tour = await db.get(Tour, tour_id)
    if tour is None or not tour.is_published:
        raise _api_error(status.HTTP_404_NOT_FOUND, "TOUR_NOT_FOUND", "Tour not found.")

    if not tour.is_free:
        result = await db.execute(
            select(Purchase).where(
                Purchase.user_id == current_user.id,
                Purchase.tour_id == tour.id,
                Purchase.status == "completed",
            )
        )
        purchase = result.scalar_one_or_none()
        if purchase is None:
            raise _api_error(
                status.HTTP_403_FORBIDDEN, "TOUR_NOT_OWNED", "You need to purchase this tour first."
            )

    stops_result = await db.execute(select(Stop).where(Stop.tour_id == tour.id).order_by(Stop.order_index))
    stops = stops_result.scalars().all()

    stop_payload = [
        StopWithAudio(
            id=stop.id,
            order_index=stop.order_index,
            name=stop.name,
            narrative_text=stop.narrative_text,
            lat=stop.lat,
            lng=stop.lng,
            trigger_radius_m=stop.trigger_radius_m,
            audio_url=_signed_audio_url(stop.audio_filename),
        )
        for stop in stops
    ]

    return TourPackage(
        tour_id=tour.id,
        name=tour.name,
        stops=stop_payload,
        signed_url_expires_in=settings.SIGNED_URL_EXPIRE_SECONDS,
    )


def _signed_audio_url(audio_filename: str) -> str:
    """Placeholder signer. Swap for real S3 presigned URLs once object storage
    is wired up — kept as a single seam so that's a one-function change."""
    return f"{settings.BASE_URL}/media/audio/{audio_filename}"
