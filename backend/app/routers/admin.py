import os
import re
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_admin
from app.models import Neighbourhood, Purchase, Stop, Tour, TourSession, User
from app.schemas.neighbourhood import NeighbourhoodCreate, NeighbourhoodOut, NeighbourhoodUpdate
from app.schemas.purchase import PurchaseOut
from app.schemas.tour import StopCreate, StopOut, TourCreate, TourDetail, TourUpdate
from app.services import notifications

router = APIRouter(prefix="/admin", tags=["admin"])


def _api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


async def _require_neighbourhood(db: AsyncSession, hood_id: uuid.UUID | None) -> None:
    if hood_id is not None and await db.get(Neighbourhood, hood_id) is None:
        raise _api_error(status.HTTP_404_NOT_FOUND, "NEIGHBOURHOOD_NOT_FOUND", "Neighbourhood not found.")


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "area"


@router.post("/neighbourhoods", response_model=NeighbourhoodOut, status_code=status.HTTP_201_CREATED)
async def create_neighbourhood(
    body: NeighbourhoodCreate, db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_admin)
):
    slug = body.slug or _slugify(body.name)
    clash = await db.execute(
        select(Neighbourhood.id).where((Neighbourhood.slug == slug) | ((Neighbourhood.name == body.name) & (Neighbourhood.city == body.city)))
    )
    if clash.first() is not None:
        raise _api_error(status.HTTP_409_CONFLICT, "NEIGHBOURHOOD_EXISTS", "A neighbourhood with this name or slug already exists.")
    hood = Neighbourhood(**body.model_dump(exclude={"slug"}), slug=slug)
    db.add(hood)
    await db.commit()
    await db.refresh(hood)
    return NeighbourhoodOut.model_validate(hood)


@router.put("/neighbourhoods/{hood_id}", response_model=NeighbourhoodOut)
async def update_neighbourhood(
    hood_id: uuid.UUID,
    body: NeighbourhoodUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    hood = await db.get(Neighbourhood, hood_id)
    if hood is None:
        raise _api_error(status.HTTP_404_NOT_FOUND, "NEIGHBOURHOOD_NOT_FOUND", "Neighbourhood not found.")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(hood, field, value)
    await db.commit()
    await db.refresh(hood)
    return NeighbourhoodOut.model_validate(hood)


@router.post("/tours", response_model=TourDetail, status_code=status.HTTP_201_CREATED)
async def create_tour(
    body: TourCreate, db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_admin)
):
    await _require_neighbourhood(db, body.neighbourhood_id)
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

    changes = body.model_dump(exclude_unset=True)
    await _require_neighbourhood(db, changes.get("neighbourhood_id"))
    for field, value in changes.items():
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

    first_publish = not tour.is_published
    tour.is_published = True
    if first_publish:
        await notifications.tour_published(db, tour)
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


# The resolved root directory all audio uploads must live under.
# Path.resolve() turns it absolute so the traversal check below is reliable.
AUDIO_ROOT = Path("media/audio").resolve()

# Strict allowlists for subfolder and filename — reject anything that
# contains path separators, dots that could navigate up, etc.
SUBFOLDER_RE = re.compile(r'^[a-z0-9-]+$')
FILENAME_RE = re.compile(r'^[a-zA-Z0-9_-]+\.mp3$')


@router.post("/audio/upload", status_code=status.HTTP_201_CREATED)
async def upload_audio(
    file: UploadFile = File(...),
    subfolder: str = "general",
    _admin: User = Depends(get_current_admin),
):
    """Upload an MP3 narration file for a tour stop.

    subfolder must be the neighbourhood slug (e.g. 'malleshwaram').
    The filename must match exactly what is stored in stops.audio_filename.
    Both are validated against strict allow-lists to prevent path traversal.
    """
    # Validate subfolder — only lowercase alphanumeric and hyphens allowed
    if not SUBFOLDER_RE.match(subfolder):
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_SUBFOLDER",
            "Subfolder must contain only lowercase letters, numbers, and hyphens.",
        )

    # Strip any path components from the filename then validate the bare name
    safe_filename = os.path.basename(file.filename or "")
    if not FILENAME_RE.match(safe_filename):
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_FILENAME",
            "Filename must match [a-zA-Z0-9_-]+.mp3 with no path separators.",
        )

    folder_path = AUDIO_ROOT / subfolder
    folder_path.mkdir(parents=True, exist_ok=True)
    file_path = folder_path / safe_filename

    # Defense-in-depth: verify the resolved path is still inside AUDIO_ROOT
    # even after the regex checks above (handles edge cases like symlinks).
    if not str(file_path.resolve()).startswith(str(AUDIO_ROOT)):
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "PATH_TRAVERSAL_DETECTED",
            "Invalid file path.",
        )

    content = await file.read()
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    return {
        "filename": f"{subfolder}/{safe_filename}",
        "path": str(file_path),
        "size_bytes": len(content),
    }
