import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Purchase, SessionEvent, Tour, TourSession, User
from app.schemas.session import (
    SessionCreate,
    SessionEventBatchRequest,
    SessionEventBatchResponse,
    TourSessionOut,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


@router.post("", response_model=TourSessionOut, status_code=status.HTTP_201_CREATED)
async def create_or_resume_session(
    body: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tour = await db.get(Tour, body.tour_id)
    if tour is None or not tour.is_published:
        raise _api_error(status.HTTP_404_NOT_FOUND, "TOUR_NOT_FOUND", "Tour not found.")

    purchase = None
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
