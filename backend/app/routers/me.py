"""The signed-in user's own aggregates: profile stats and passport stamps."""
import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import String, cast, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.core.security import hash_password
from app.models import (
    Neighbourhood,
    OtpRequest,
    Purchase,
    SavedTour,
    Tour,
    TourComment,
    TourLike,
    TourRating,
    TourSession,
    User,
    UserLoginSession,
)
from app.schemas.me import (
    DeleteAccountRequest,
    Passport,
    PassportStamp,
    PreferencesUpdate,
    ProfileStats,
    ProfileUpdate,
)
from app.schemas.user import UserOut
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
                Tour.name.label("tour_name"),
            )
            .join(Tour, Tour.id == TourSession.tour_id)
            .where(TourSession.user_id == user.id, TourSession.completed.is_(True))
        )
    ).all()


@router.get("/stats", response_model=ProfileStats)
async def my_stats(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """The three numbers on the Profile screen (plus a couple of extras)."""
    rows = await _completed_walks(db, current_user)
    reviews = (
        await db.execute(select(func.count()).select_from(TourRating).where(TourRating.user_id == current_user.id))
    ).scalar_one()
    return ProfileStats(
        walks_completed=len(rows),
        distance_km=round(sum(float(r.distance_km or 0) for r in rows), 1),
        stops_visited=sum(r.stops_visited for r in rows),
        listening_minutes=sum(r.duration_min or 0 for r in rows),
        neighbourhoods_stamped=len({r.neighbourhood_id for r in rows if r.neighbourhood_id}),
        reviews_count=reviews,
    )


@router.get("/passport", response_model=Passport)
async def my_passport(
    city: str = Query(default="Bangalore"),
    include_empty: bool = Query(default=True, description="Also show areas with no published walk yet (locked slots)"),
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
    first_name: dict[uuid.UUID, str] = {}
    for row in await _completed_walks(db, current_user):
        if row.neighbourhood_id is None:
            continue
        completed[row.neighbourhood_id] += 1
        if row.completed_at and (row.neighbourhood_id not in first_at or row.completed_at < first_at[row.neighbourhood_id]):
            first_at[row.neighbourhood_id] = row.completed_at
            first_name[row.neighbourhood_id] = row.tour_name

    stamps = []
    for hood in hoods:
        if not include_empty and not totals.get(hood.id) and not completed.get(hood.id):
            continue  # nothing to collect there yet
        stamps.append(
            PassportStamp(
                neighbourhood=NeighbourhoodRef.model_validate(hood),
                cover_image=hood.cover_image,
                emoji=hood.emoji,
                walk_name=first_name.get(hood.id),
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


# ---------------------------------------------------------------------------
# Profile, preferences, export, deletion
# ---------------------------------------------------------------------------

def _api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


@router.get("", response_model=UserOut)
async def my_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("", response_model=UserOut)
async def update_profile(
    body: ProfileUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Edit name / username. Email is not editable (changing it needs re-verification)."""
    changes = body.model_dump(exclude_unset=True)
    if "full_name" in changes:
        if changes["full_name"] is None:
            raise _api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "VALIDATION_ERROR", "full_name: cannot be empty.")
        current_user.full_name = changes["full_name"]
    if "username" in changes:
        username = changes["username"]
        if username is not None:
            taken = (
                await db.execute(select(User.id).where(User.username == username, User.id != current_user.id))
            ).first()
            if taken is not None:
                raise _api_error(status.HTTP_409_CONFLICT, "USERNAME_TAKEN", "That username is taken.")
        current_user.username = username
    try:
        await db.commit()
    except IntegrityError:  # lost a race for the same username
        await db.rollback()
        raise _api_error(status.HTTP_409_CONFLICT, "USERNAME_TAKEN", "That username is taken.")
    await db.refresh(current_user)
    return current_user


@router.patch("/preferences", response_model=UserOut)
async def update_preferences(
    body: PreferencesUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(current_user, field, value)
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/export")
async def export_my_data(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """"Download my data": everything we hold about the user, as JSON.
    Never includes password hashes, tokens or other people's data."""
    uid = current_user.id
    tour_names = {t[0]: t[1] for t in (await db.execute(select(Tour.id, Tour.name))).all()}

    def iso(value):
        return value.astimezone(timezone.utc).isoformat() if value else None

    purchases = (await db.execute(select(Purchase).where(Purchase.user_id == uid).order_by(Purchase.created_at))).scalars().all()
    sessions = (await db.execute(select(TourSession).where(TourSession.user_id == uid).order_by(TourSession.started_at))).scalars().all()
    ratings = (await db.execute(select(TourRating).where(TourRating.user_id == uid))).scalars().all()
    comments = (await db.execute(select(TourComment).where(TourComment.user_id == uid, TourComment.is_deleted.is_(False)))).scalars().all()
    likes = (await db.execute(select(TourLike).where(TourLike.user_id == uid))).scalars().all()
    saved = (await db.execute(select(SavedTour).where(SavedTour.user_id == uid))).scalars().all()

    payload = {
        "exported_at": iso(datetime.now(timezone.utc)),
        "profile": {
            "id": str(current_user.id),
            "email": current_user.email,
            "full_name": current_user.full_name,
            "username": current_user.username,
            "created_at": iso(current_user.created_at),
        },
        "consent": {
            "terms_version": current_user.terms_version,
            "terms_accepted_at": iso(current_user.terms_accepted_at),
            "marketing_opt_in": current_user.marketing_opt_in,
            "analytics_opt_in": current_user.analytics_opt_in,
            "notifications_enabled": current_user.notifications_enabled,
        },
        "purchases": [
            {
                "booking_ref": p.booking_ref,
                "tour": tour_names.get(p.tour_id),
                "amount_paise": p.amount_paise,
                "status": p.status,
                "purchased_at": iso(p.created_at),
            }
            for p in purchases
        ],
        "walks": [
            {
                "tour": tour_names.get(s.tour_id),
                "started_at": iso(s.started_at),
                "completed": s.completed,
                "completed_at": iso(s.completed_at),
                "stops_visited": s.stops_visited,
            }
            for s in sessions
        ],
        "ratings": [{"tour": tour_names.get(r.tour_id), "rating": r.rating} for r in ratings],
        "comments": [{"tour": tour_names.get(c.tour_id), "text": c.content, "posted_at": iso(c.created_at)} for c in comments],
        "likes": [{"tour": tour_names.get(l.tour_id), "liked_at": iso(l.liked_at)} for l in likes],
        "saved_tours": [{"tour": tour_names.get(s.tour_id), "saved_at": iso(s.saved_at)} for s in saved],
    }
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="nob-my-data.json"'},
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(
    body: DeleteAccountRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Permanently delete the account: personal data is erased and every device is signed out.

    Purchase, payment and walk records are kept (accounting and the licence history)
    but are no longer linked to any identifiable person: the row is anonymised.
    Admin accounts cannot be deleted this way."""
    if current_user.role == "admin":
        raise _api_error(status.HTTP_409_CONFLICT, "ADMIN_CANNOT_BE_DELETED", "Admin accounts can't be deleted here.")
    uid, old_email = current_user.id, current_user.email

    await db.execute(delete(TourComment).where(TourComment.user_id == uid))
    await db.execute(delete(TourLike).where(TourLike.user_id == uid))
    await db.execute(delete(TourRating).where(TourRating.user_id == uid))
    await db.execute(delete(SavedTour).where(SavedTour.user_id == uid))
    await db.execute(delete(OtpRequest).where(OtpRequest.email == old_email.lower()))
    await db.execute(
        update(UserLoginSession)
        .where(UserLoginSession.user_id == uid)
        .values(is_active=False, refresh_token=func.concat("revoked-", cast(UserLoginSession.id, String)))
    )
    current_user.email = f"deleted-{uid.hex}@deleted.invalid"
    current_user.full_name = None
    current_user.username = None
    current_user.avatar_url = None
    current_user.password_hash = hash_password(uuid.uuid4().hex)
    current_user.marketing_opt_in = False
    current_user.analytics_opt_in = False
    current_user.notifications_enabled = False
    current_user.deleted_at = datetime.now(timezone.utc)
    await db.commit()
