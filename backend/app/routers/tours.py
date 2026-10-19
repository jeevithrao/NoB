import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, get_current_user_optional
from app.models import Neighbourhood, Purchase, Stop, Tour, TourLike, TourSession, User
from app.schemas.tour import StopWithAudio, TourDetail, TourListItem, TourPackage
from app.services.catalog import to_list_items

router = APIRouter(prefix="/tours", tags=["tours"])

# Shared with purchases.py via import — single source of truth for the copy
# shown when a device-binding conflict is detected.
_BOUND_TO_OTHER_DEVICE_MSG = (
    "This tour was downloaded on another device. Re-download here to move it — "
    "your other device will need to sign in again to use it."
)


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
    result = await db.execute(select(func.count(TourLike.user_id)).where(TourLike.tour_id == tour_id))
    return result.scalar_one()


SortKey = Literal["newest", "price_asc", "price_desc", "duration", "popular"]


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("", response_model=list[TourListItem])
async def list_tours(
    city: str = Query(default="Bangalore"),
    q: str | None = Query(default=None, max_length=100, description="Search name, description, neighbourhood"),
    neighbourhood: str | None = Query(default=None, description="Neighbourhood slug or id"),
    free: bool | None = Query(default=None, description="true = only free tours, false = only paid"),
    min_price: int | None = Query(default=None, ge=0, description="paise"),
    max_price: int | None = Query(default=None, ge=0, description="paise"),
    sort: SortKey = Query(default="newest"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    stmt = select(Tour).where(Tour.city == city, Tour.is_published.is_(True))

    if q and q.strip():
        like = f"%{_escape_like(q.strip())}%"
        stmt = stmt.where(
            or_(
                Tour.name.ilike(like, escape="\\"),
                Tour.description.ilike(like, escape="\\"),
                Tour.neighbourhood.has(Neighbourhood.name.ilike(like, escape="\\")),
            )
        )
    if neighbourhood:
        try:
            stmt = stmt.where(Tour.neighbourhood_id == uuid.UUID(neighbourhood))
        except ValueError:
            stmt = stmt.where(Tour.neighbourhood.has(Neighbourhood.slug == neighbourhood))
    if free is True:
        stmt = stmt.where(Tour.is_free.is_(True))
    elif free is False:
        stmt = stmt.where(Tour.is_free.is_(False))
    if min_price is not None:
        stmt = stmt.where(Tour.price_paise >= min_price)
    if max_price is not None:
        stmt = stmt.where(Tour.price_paise <= max_price)

    if sort == "price_asc":
        order = [Tour.price_paise.asc()]
    elif sort == "price_desc":
        order = [Tour.price_paise.desc()]
    elif sort == "duration":
        order = [Tour.duration_min.asc().nulls_last()]
    elif sort == "popular":
        likes = select(func.count()).where(TourLike.tour_id == Tour.id).correlate(Tour).scalar_subquery()
        order = [likes.desc()]
    else:
        order = [Tour.created_at.desc()]
    stmt = stmt.order_by(*order, Tour.id).limit(limit).offset(offset)

    tours = (await db.execute(stmt)).scalars().unique().all()
    return await to_list_items(db, current_user, tours)


@router.get("/featured", response_model=list[TourListItem])
async def featured_tours(
    city: str = Query(default="Bangalore"),
    limit: int = Query(default=10, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """The "Featured walks" carousel on Explore."""
    result = await db.execute(
        select(Tour)
        .where(Tour.city == city, Tour.is_published.is_(True), Tour.is_featured.is_(True))
        .order_by(Tour.created_at.desc(), Tour.id)
        .limit(limit)
    )
    return await to_list_items(db, current_user, result.scalars().unique().all())


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
    if tour.preview_audio_filename:
        detail.preview_audio_url = _signed_audio_url(tour.preview_audio_filename)

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
    x_device_id: str = Header(..., alias="X-Device-Id"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stop manifest + signed audio URLs for offline download (Feature Spec 3).
    Requires a completed purchase unless the tour is free. The device header
    is compared against the bound device_id to enforce the one-device-at-a-time
    business rule (Business Rules §3a)."""
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
        # Device binding check — only reject if already bound to a *different* device.
        # If unbound (device_id is None), binding happens via /bind-device before
        # the walk starts; this gate just stops a second device from downloading.
        if purchase.device_id is not None and purchase.device_id != x_device_id:
            raise _api_error(
                status.HTTP_409_CONFLICT,
                "BOUND_TO_OTHER_DEVICE",
                _BOUND_TO_OTHER_DEVICE_MSG,
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


from app.core.security import sign_media_path


def _signed_audio_url(audio_filename: str) -> str:
    """Returns a time-limited HMAC-signed URL for the audio file.

    The URL is valid for settings.SIGNED_URL_EXPIRE_SECONDS seconds. The mobile
    app re-fetches the package if the URL has expired (the session TTL should
    be set shorter than the signed URL TTL to avoid mid-walk expiry).
    Swap the BASE_URL prefix for an S3/CDN domain once object storage is live.
    """
    path = f"/media/audio/{audio_filename}"
    qs = sign_media_path(path, settings.SIGNED_URL_EXPIRE_SECONDS)
    return f"{settings.BASE_URL}{path}{qs}"

