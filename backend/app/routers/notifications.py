"""The bell: list, mark read, dismiss."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Notification, User
from app.schemas.notification import NotificationList, NotificationOut

router = APIRouter(prefix="/me/notifications", tags=["notifications"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": "NOTIFICATION_NOT_FOUND", "message": "Notification not found."}},
    )


@router.get("", response_model=NotificationList)
async def list_notifications(
    limit: int = Query(default=50, ge=1, le=100),
    unread_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Newest first. `unread_count` always covers everything, not just this page."""
    stmt = select(Notification).where(Notification.user_id == current_user.id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    items = (await db.execute(stmt.order_by(Notification.created_at.desc(), Notification.id).limit(limit))).scalars().all()
    unread = (
        await db.execute(
            select(func.count()).select_from(Notification).where(
                Notification.user_id == current_user.id, Notification.is_read.is_(False)
            )
        )
    ).scalar_one()
    return NotificationList(unread_count=unread, items=[NotificationOut.model_validate(n) for n in items])


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(
    notification_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    item = await db.get(Notification, notification_id)
    if item is None or item.user_id != current_user.id:
        raise _not_found()
    item.is_read = True
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss(
    notification_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        delete(Notification).where(Notification.id == notification_id, Notification.user_id == current_user.id)
    )
    if result.rowcount == 0:
        raise _not_found()
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
