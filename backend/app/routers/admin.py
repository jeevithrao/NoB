import os
import uuid

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_admin
from app.models import Purchase, Stop, Tour, TourSession, User
from app.schemas.purchase import PurchaseOut
from app.schemas.tour import StopCreate, StopOut, TourCreate, TourDetail, TourUpdate

router = APIRouter(prefix="/admin", tags=["admin"])


def _api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


@router.post("/tours", response_model=TourDetail, status_code=status.HTTP_201_CREATED)
async def create_tour(
    body: TourCreate, db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_admin)
):
    tour = Tour(**body.model_dump())
    db.add(tour)
    await db.commit()
    await db.refresh(tour)
    detail = TourDetail.model_validate(tour)
    detail.stop_count = 0
    return detail


@router.put("/tours/{tour_id}", response_model=TourDetail)
async def update_tour(
    tour_id: uuid.UUID,
    body: TourUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    tour = await db.get(Tour, tour_id)
    if tour is None:
        raise _api_error(status.HTTP_404_NOT_FOUND, "TOUR_NOT_FOUND", "Tour not found.")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(tour, field, value)

    await db.commit()
    await db.refresh(tour)
    stop_count = await db.execute(select(Stop).where(Stop.tour_id == tour.id))
    detail = TourDetail.model_validate(tour)
    detail.stop_count = len(stop_count.scalars().all())
    return detail


@router.post("/tours/{tour_id}/publish", response_model=TourDetail)
async def publish_tour(
    tour_id: uuid.UUID, db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_admin)
):
    tour = await db.get(Tour, tour_id)
    if tour is None:
        raise _api_error(status.HTTP_404_NOT_FOUND, "TOUR_NOT_FOUND", "Tour not found.")

    stops_result = await db.execute(select(Stop).where(Stop.tour_id == tour.id))
    stops = stops_result.scalars().all()
    if not stops:
        raise _api_error(
            status.HTTP_400_BAD_REQUEST, "NO_STOPS", "Add at least one stop before publishing a tour."
        )

    tour.is_published = True
    await db.commit()
    await db.refresh(tour)
    detail = TourDetail.model_validate(tour)
    detail.stop_count = len(stops)
    return detail


@router.post("/tours/{tour_id}/stops", response_model=StopOut, status_code=status.HTTP_201_CREATED)
async def add_stop(
    tour_id: uuid.UUID,
    body: StopCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    tour = await db.get(Tour, tour_id)
    if tour is None:
        raise _api_error(status.HTTP_404_NOT_FOUND, "TOUR_NOT_FOUND", "Tour not found.")

    stop = Stop(tour_id=tour_id, **body.model_dump())
    db.add(stop)
    await db.commit()
    await db.refresh(stop)
    return stop


@router.get("/purchases", response_model=list[PurchaseOut])
async def list_purchases(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    result = await db.execute(select(Purchase).order_by(Purchase.created_at.desc()))
    return result.scalars().all()


@router.post("/sessions/{session_id}/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """Support tool for GPS-trigger-bug recovery (Business Rules §4) — resets
    progress on a stuck session without requiring the user to repurchase."""
    session = await db.get(TourSession, session_id)
    if session is None:
        raise _api_error(status.HTTP_404_NOT_FOUND, "SESSION_NOT_FOUND", "Session not found.")

    session.stops_visited = 0
    session.completed = False
    session.completed_at = None
    session.is_resumable = True

    if session.purchase_id is not None:
        purchase = await db.get(Purchase, session.purchase_id)
        if purchase is not None:
            purchase.is_locked = False
            purchase.locked_at = None

    await db.commit()


@router.post("/audio/upload", status_code=status.HTTP_201_CREATED)
async def upload_audio(
    file: UploadFile = File(...),
    subfolder: str = "general",
    _admin: User = Depends(get_current_admin),
):
    """Upload an MP3 audio file for a tour stop.
    subfolder should be the neighbourhood slug, e.g. 'malleshwaram'.
    The filename must match exactly what's stored in the stops.audio_filename column.
    """
    if not (file.filename or "").lower().endswith(".mp3"):
        raise _api_error(status.HTTP_400_BAD_REQUEST, "INVALID_FILE_TYPE", "Only .mp3 files are accepted.")

    folder_path = os.path.join("media", "audio", subfolder)
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, file.filename)

    content = await file.read()
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    return {
        "filename": f"{subfolder}/{file.filename}",
        "path": file_path,
        "size_bytes": len(content),
    }
