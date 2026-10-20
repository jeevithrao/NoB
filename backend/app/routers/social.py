import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.text import display_name
from app.database import get_db
from app.dependencies import get_current_user, get_current_user_optional
from app.models import SavedTour, Tour, TourComment, TourLike, TourRating, TourSession, User
from app.schemas.social import (
    CommentCreate,
    CommentOut,
    LikeStatus,
    RatingIn,
    RatingSummary,
    ReviewOut,
    SavedTourCreate,
    SavedTourOut,
)
from app.services.catalog import rating_stats

router = APIRouter(tags=["social"])


def _api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


async def _published_tour(db: AsyncSession, tour_id: uuid.UUID) -> Tour:
    """Hidden (unpublished) tours do not exist as far as users are concerned."""
    tour = await db.get(Tour, tour_id)
    if tour is None or not tour.is_published:
        raise _api_error(status.HTTP_404_NOT_FOUND, "TOUR_NOT_FOUND", "Tour not found.")
    return tour


# ---- Saved tours (wishlist) ----


@router.post("/saved-tours", response_model=SavedTourOut, status_code=status.HTTP_201_CREATED)
async def save_tour(
    body: SavedTourCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _published_tour(db, body.tour_id)

    await db.execute(
        pg_insert(SavedTour).values(user_id=current_user.id, tour_id=body.tour_id).on_conflict_do_nothing()
    )
    await db.commit()
    return await db.get(SavedTour, {"user_id": current_user.id, "tour_id": body.tour_id}, populate_existing=True)


@router.delete("/saved-tours/{tour_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unsave_tour(
    tour_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    saved = await db.get(SavedTour, {"user_id": current_user.id, "tour_id": tour_id})
    if saved is not None:
        await db.delete(saved)
        await db.commit()


@router.get("/saved-tours", response_model=list[SavedTourOut])
async def list_saved_tours(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(SavedTour).where(SavedTour.user_id == current_user.id))
    return result.scalars().all()


# ---- Likes ----


async def _require_completed(db: AsyncSession, user: User, tour_id: uuid.UUID, what: str) -> None:
    if not await _has_completed_tour(db, user.id, tour_id):
        raise _api_error(
            status.HTTP_403_FORBIDDEN,
            "TOUR_NOT_COMPLETED",
            f"Finish walking this tour before {what}.",
        )


@router.post("/tours/{tour_id}/like", response_model=LikeStatus)
async def like_tour(
    tour_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Likes are a post-walk reaction (PRD feature 12): completed walkers only."""
    await _published_tour(db, tour_id)
    await _require_completed(db, current_user, tour_id, "liking it")

    # Atomic: two quick taps (or retries) can't collide on the primary key.
    await db.execute(
        pg_insert(TourLike).values(user_id=current_user.id, tour_id=tour_id).on_conflict_do_nothing()
    )
    await db.commit()
    return await _like_status(db, tour_id, liked=True)


@router.delete("/tours/{tour_id}/like", response_model=LikeStatus)
async def unlike_tour(
    tour_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = await db.get(TourLike, {"user_id": current_user.id, "tour_id": tour_id})
    if existing is not None:
        await db.delete(existing)
        await db.commit()
    return await _like_status(db, tour_id, liked=False)


async def _like_status(db: AsyncSession, tour_id: uuid.UUID, *, liked: bool) -> LikeStatus:
    count = await db.execute(select(func.count()).select_from(TourLike).where(TourLike.tour_id == tour_id))
    return LikeStatus(liked=liked, like_count=count.scalar_one())


# ---- Ratings ----
# Business rule: like comments, only walkers who completed the tour may rate it.


async def _rating_summary(db: AsyncSession, tour_id: uuid.UUID, user: User | None) -> RatingSummary:
    avg, count = (await rating_stats(db, [tour_id])).get(tour_id, (None, 0))
    rows = await db.execute(
        select(TourRating.rating, func.count()).where(TourRating.tour_id == tour_id).group_by(TourRating.rating)
    )
    distribution = {star: 0 for star in range(1, 6)}
    distribution.update({r[0]: r[1] for r in rows.all()})
    mine = await db.get(TourRating, {"user_id": user.id, "tour_id": tour_id}) if user else None
    return RatingSummary(avg_rating=avg, rating_count=count, my_rating=mine.rating if mine else None, distribution=distribution)


@router.put("/tours/{tour_id}/rating", response_model=RatingSummary)
async def rate_tour(
    tour_id: uuid.UUID,
    body: RatingIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set or change your 1-5 rating. Completed walkers only."""
    await _published_tour(db, tour_id)
    await _require_completed(db, current_user, tour_id, "rating it")

    await db.execute(
        pg_insert(TourRating)
        .values(user_id=current_user.id, tour_id=tour_id, rating=body.rating)
        .on_conflict_do_update(
            index_elements=[TourRating.user_id, TourRating.tour_id],
            set_={"rating": body.rating, "updated_at": func.now()},
        )
    )
    await db.commit()
    return await _rating_summary(db, tour_id, current_user)


@router.get("/tours/{tour_id}/rating", response_model=RatingSummary)
async def get_rating(
    tour_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    await _published_tour(db, tour_id)
    return await _rating_summary(db, tour_id, current_user)


# ---- Comments ----
# Business rule: only users who completed the tour may comment.


async def _has_completed_tour(db: AsyncSession, user_id: uuid.UUID, tour_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(TourSession).where(
            TourSession.user_id == user_id, TourSession.tour_id == tour_id, TourSession.completed.is_(True)
        )
    )
    return result.scalars().first() is not None


@router.post("/tours/{tour_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
async def create_comment(
    tour_id: uuid.UUID,
    body: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _published_tour(db, tour_id)
    await _require_completed(db, current_user, tour_id, "leaving a comment")

    comment = TourComment(user_id=current_user.id, tour_id=tour_id, content=body.comment_text)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    return CommentOut(
        id=comment.id,
        user_id=comment.user_id,
        user_name=display_name(current_user.full_name),
        content=comment.content,
        created_at=comment.created_at,
    )


@router.get("/tours/{tour_id}/comments", response_model=list[CommentOut])
async def list_comments(tour_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await _published_tour(db, tour_id)
    result = await db.execute(
        select(TourComment)
        .where(TourComment.tour_id == tour_id, TourComment.is_deleted.is_(False))
        .order_by(TourComment.created_at.desc())
    )
    comments = result.scalars().all()
    if not comments:
        return []

    # Batch query users to prevent N+1 queries (Phase 3 Task 4)
    user_ids = list({comment.user_id for comment in comments})
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}

    return [
        CommentOut(
            id=comment.id,
            user_id=comment.user_id,
            user_name=display_name(users_map[comment.user_id].full_name) if comment.user_id in users_map else display_name(None),
            content=comment.content,
            created_at=comment.created_at,
        )
        for comment in comments
    ]


@router.delete("/tours/{tour_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    tour_id: uuid.UUID,
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a comment from a tour.

    Permissions (Phase 3 Task 5):
    - Comment author: allowed
    - Admin user: allowed
    - Other non-admin user: 403 FORBIDDEN
    """
    comment = await db.get(TourComment, comment_id)
    if comment is None or comment.is_deleted or comment.tour_id != tour_id:
        raise _api_error(status.HTTP_404_NOT_FOUND, "COMMENT_NOT_FOUND", "Comment not found.")

    if current_user.id != comment.user_id and current_user.role != "admin":
        raise _api_error(
            status.HTTP_403_FORBIDDEN,
            "FORBIDDEN",
            "You do not have permission to delete this comment.",
        )

    comment.is_deleted = True
    await db.commit()



# ---- "What walkers say" ----


@router.get("/reviews", response_model=list[ReviewOut])
async def recent_reviews(
    tour_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Newest comments on published tours, paired with the author's star rating
    for that tour, shown with first name + last initial only."""
    stmt = (
        select(TourComment, Tour.name, User.full_name, TourRating.rating)
        .join(Tour, Tour.id == TourComment.tour_id)
        .join(User, User.id == TourComment.user_id)
        .outerjoin(
            TourRating, (TourRating.user_id == TourComment.user_id) & (TourRating.tour_id == TourComment.tour_id)
        )
        .where(TourComment.is_deleted.is_(False), Tour.is_published.is_(True))
        .order_by(TourComment.created_at.desc(), TourComment.id)
        .limit(limit)
    )
    if tour_id is not None:
        stmt = stmt.where(TourComment.tour_id == tour_id)
    rows = (await db.execute(stmt)).all()
    return [
        ReviewOut(
            id=c.id,
            tour_id=c.tour_id,
            tour_name=tour_name,
            user_name=display_name(full_name),
            rating=rating,
            content=c.content,
            created_at=c.created_at,
        )
        for c, tour_name, full_name, rating in rows
    ]
