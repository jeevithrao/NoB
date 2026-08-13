import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import SavedTour, Tour, TourComment, TourLike, TourSession, User
from app.schemas.social import CommentCreate, CommentOut, LikeStatus, SavedTourCreate, SavedTourOut

router = APIRouter(tags=["social"])


def _api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


# ---- Saved tours (wishlist) ----


@router.post("/saved-tours", response_model=SavedTourOut, status_code=status.HTTP_201_CREATED)
async def save_tour(
    body: SavedTourCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tour = await db.get(Tour, body.tour_id)
    if tour is None:
        raise _api_error(status.HTTP_404_NOT_FOUND, "TOUR_NOT_FOUND", "Tour not found.")

    existing = await db.get(SavedTour, {"user_id": current_user.id, "tour_id": body.tour_id})
    if existing is not None:
        return existing

    saved = SavedTour(user_id=current_user.id, tour_id=body.tour_id)
    db.add(saved)
    await db.commit()
    await db.refresh(saved)
    return saved


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


@router.post("/tours/{tour_id}/like", response_model=LikeStatus)
async def like_tour(
    tour_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tour = await db.get(Tour, tour_id)
    if tour is None:
        raise _api_error(status.HTTP_404_NOT_FOUND, "TOUR_NOT_FOUND", "Tour not found.")

    existing = await db.get(TourLike, {"user_id": current_user.id, "tour_id": tour_id})
    if existing is None:
        db.add(TourLike(user_id=current_user.id, tour_id=tour_id))
        await db.commit()

    return await _like_status(db, tour_id)


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
    return await _like_status(db, tour_id)


async def _like_status(db: AsyncSession, tour_id: uuid.UUID) -> LikeStatus:
    from sqlalchemy import func

    count_result = await db.execute(select(func.count()).select_from(TourLike).where(TourLike.tour_id == tour_id))
    return LikeStatus(liked=True, like_count=count_result.scalar_one())


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
    tour = await db.get(Tour, tour_id)
    if tour is None:
        raise _api_error(status.HTTP_404_NOT_FOUND, "TOUR_NOT_FOUND", "Tour not found.")

    if not await _has_completed_tour(db, current_user.id, tour_id):
        raise _api_error(
            status.HTTP_403_FORBIDDEN,
            "TOUR_NOT_COMPLETED",
            "Finish walking this tour before leaving a comment.",
        )

    comment = TourComment(user_id=current_user.id, tour_id=tour_id, content=body.comment_text)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    return CommentOut(
        id=comment.id,
        user_id=comment.user_id,
        user_name=current_user.full_name,
        content=comment.content,
        created_at=comment.created_at,
    )


@router.get("/tours/{tour_id}/comments", response_model=list[CommentOut])
async def list_comments(tour_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
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
            user_name=users_map[comment.user_id].full_name if comment.user_id in users_map else None,
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

