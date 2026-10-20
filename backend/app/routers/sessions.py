import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_login_device
from app.models import Purchase, SessionEvent, Stop, Tour, TourComment, TourLike, TourRating, TourSession, User
from app.schemas.session import (
    SessionCreate,
    SessionEventBatchRequest,
    SessionEventBatchResponse,
    SessionSummary,
    TourSessionOut,
)
from app.routers.tours import _BOUND_TO_OTHER_DEVICE_MSG
from app.schemas.tour import NeighbourhoodRef
from app.services.catalog import rating_stats

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


@router.post("", response_model=TourSessionOut, status_code=status.HTTP_201_CREATED)
async def create_or_resume_session(
    body: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    login_device: str = Depends(get_login_device),
):
    tour = await db.get(Tour, body.tour_id)
    if tour is None or not tour.is_published:
        raise _api_error(status.HTTP_404_NOT_FOUND, "TOUR_NOT_FOUND", "Tour not found.")

    result = await db.execute(
        select(Purchase).where(
            Purchase.user_id == current_user.id,
            Purchase.tour_id == tour.id,
            Purchase.status == "completed",
        )
    )
    purchase = result.scalar_one_or_none()
    if purchase is None and not tour.is_free:
        raise _api_error(status.HTTP_403_FORBIDDEN, "TOUR_NOT_OWNED", "You need to purchase this tour first.")

    existing_result = await db.execute(
        select(TourSession)
        .where(TourSession.user_id == current_user.id, TourSession.tour_id == tour.id)
        .order_by(TourSession.started_at.desc())
    )
    sessions = existing_result.scalars().all()

    # License already consumed — Business Rules §1: once completed, no replay
    # without a fresh purchase.
    if any(s.completed for s in sessions):
        raise _api_error(
            status.HTTP_403_FORBIDDEN,
            "TOUR_ALREADY_COMPLETED",
            "This tour's one playback has already been used. Purchase again to replay it.",
        )

    # A purchase bound to another device can't be walked from this one (Business
    # Rules 3a). The user can move it from My Bookings (POST .../rebind-device).
    if purchase is not None and purchase.device_id is not None and purchase.device_id != login_device:
        raise _api_error(status.HTTP_409_CONFLICT, "BOUND_TO_OTHER_DEVICE", _BOUND_TO_OTHER_DEVICE_MSG)

    # Resume the existing in-progress walk rather than starting a new row —
    # interruptions (GPS loss, crash, dead battery) never consume the license.
    in_progress = next((s for s in sessions if not s.completed), None)
    if in_progress is not None:
        return in_progress

    session = TourSession(
        user_id=current_user.id,
        tour_id=tour.id,
        purchase_id=purchase.id if purchase else None,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.post("/{session_id}/events/batch", response_model=SessionEventBatchResponse)
async def submit_events_batch(
    session_id: uuid.UUID,
    body: SessionEventBatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await db.get(TourSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise _api_error(status.HTTP_404_NOT_FOUND, "SESSION_NOT_FOUND", "Session not found.")
    if session.completed:
        raise _api_error(status.HTTP_409_CONFLICT, "SESSION_LOCKED", "This walk is already completed.")

    if not body.events:
        return SessionEventBatchResponse(accepted=0, duplicate=0, session=session)

    # Events may only reference stops of this session's own tour; otherwise a
    # client could inflate stops_visited with stops from another walk.
    valid_stops = set(
        (await db.execute(select(Stop.id).where(Stop.tour_id == session.tour_id))).scalars().all()
    )
    if any(event.stop_id not in valid_stops for event in body.events):
        raise _api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_STOP", "Event references a stop that is not part of this tour.")

    incoming_ids = [event.client_event_id for event in body.events]
    existing_result = await db.execute(
        select(SessionEvent.client_event_id).where(SessionEvent.client_event_id.in_(incoming_ids))
    )
    already_seen = set(existing_result.scalars().all())

    accepted = 0
    duplicate = 0
    for event in body.events:
        if event.client_event_id in already_seen:
            duplicate += 1
            continue
        db.add(
            SessionEvent(
                session_id=session.id,
                stop_id=event.stop_id,
                client_event_id=event.client_event_id,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
            )
        )
        already_seen.add(event.client_event_id)  # guards against dupes within the same batch
        accepted += 1

    # stops_visited = distinct stops this session has an 'arrived' event for.
    distinct_stops = await db.execute(
        select(func.count(func.distinct(SessionEvent.stop_id))).where(
            SessionEvent.session_id == session.id, SessionEvent.event_type == "arrived"
        )
    )
    session.stops_visited = distinct_stops.scalar_one()
    await db.commit()
    await db.refresh(session)

    return SessionEventBatchResponse(accepted=accepted, duplicate=duplicate, session=session)


@router.post("/{session_id}/complete", response_model=TourSessionOut)
async def complete_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await db.get(TourSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise _api_error(status.HTTP_404_NOT_FOUND, "SESSION_NOT_FOUND", "Session not found.")
    if session.completed:
        return session

    session.completed = True
    session.is_resumable = False
    session.completed_at = datetime.now(timezone.utc)

    if session.purchase_id is not None:
        purchase = await db.get(Purchase, session.purchase_id)
        if purchase is not None:
            purchase.is_locked = True
            purchase.locked_at = session.completed_at

    await db.commit()
    await db.refresh(session)
    return session


@router.get("/{session_id}/summary", response_model=SessionSummary)
async def session_summary(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Everything the Walk-complete screen shows, in one call."""
    session = await db.get(TourSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise _api_error(status.HTTP_404_NOT_FOUND, "SESSION_NOT_FOUND", "Session not found.")
    tour = await db.get(Tour, session.tour_id)

    stop_count = (await db.execute(select(func.count()).select_from(Stop).where(Stop.tour_id == tour.id))).scalar_one()
    avg, count = (await rating_stats(db, [tour.id])).get(tour.id, (None, 0))
    mine = await db.get(TourRating, {"user_id": current_user.id, "tour_id": tour.id})
    liked = await db.get(TourLike, {"user_id": current_user.id, "tour_id": tour.id}) is not None
    commented = (
        await db.execute(
            select(TourComment.id).where(
                TourComment.user_id == current_user.id, TourComment.tour_id == tour.id, TourComment.is_deleted.is_(False)
            ).limit(1)
        )
    ).first() is not None

    stamp_earned = False
    if session.completed and tour.neighbourhood_id is not None:
        earlier = await db.execute(
            select(TourSession.id)
            .join(Tour, Tour.id == TourSession.tour_id)
            .where(
                TourSession.user_id == current_user.id,
                TourSession.completed.is_(True),
                TourSession.id != session.id,
                Tour.neighbourhood_id == tour.neighbourhood_id,
                TourSession.completed_at <= session.completed_at,
            )
            .limit(1)
        )
        stamp_earned = earlier.first() is None

    return SessionSummary(
        session_id=session.id,
        tour_id=tour.id,
        tour_name=tour.name,
        completed=session.completed,
        completed_at=session.completed_at,
        stops_visited=session.stops_visited,
        stop_count=stop_count,
        distance_km=float(tour.distance_km) if tour.distance_km is not None else None,
        duration_min=tour.duration_min,
        neighbourhood=NeighbourhoodRef.model_validate(tour.neighbourhood) if tour.neighbourhood else None,
        stamp_earned=stamp_earned,
        avg_rating=avg,
        rating_count=count,
        my_rating=mine.rating if mine else None,
        liked=liked,
        commented=commented,
    )
