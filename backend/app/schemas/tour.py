import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase

TourStatus = Literal["not_purchased", "purchased", "in_progress", "completed_locked"]


class TourListItem(ORMBase):
    id: uuid.UUID
    name: str
    description: str | None
    city: str
    cover_image: str | None
    duration_min: int | None
    distance_km: Decimal | None
    price_paise: int
    is_free: bool
    status: TourStatus = "not_purchased"
    like_count: int = 0


class TourDetail(TourListItem):
    is_published: bool
    stop_count: int = 0
    purchase_id: uuid.UUID | None = None


class StopOut(ORMBase):
    id: uuid.UUID
    order_index: int
    name: str
    narrative_text: str | None
    lat: Decimal
    lng: Decimal
    trigger_radius_m: int


class StopWithAudio(StopOut):
    audio_url: str


class TourPackage(BaseModel):
    """What the client downloads for fully-offline playback."""

    tour_id: uuid.UUID
    name: str
    stops: list[StopWithAudio]
    signed_url_expires_in: int


# ---- Admin create/update ----


class StopCreate(BaseModel):
    order_index: int
    name: str
    narrative_text: str | None = None
    lat: Decimal
    lng: Decimal
    trigger_radius_m: int = Field(default=30, ge=20)
    audio_filename: str


class TourCreate(BaseModel):
    name: str
    description: str | None = None
    city: str = "Bangalore"
    cover_image: str | None = None
    duration_min: int | None = None
    distance_km: Decimal | None = None
    price_paise: int = 0
    is_free: bool = False


class TourUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    city: str | None = None
    cover_image: str | None = None
    duration_min: int | None = None
    distance_km: Decimal | None = None
    price_paise: int | None = None
    is_free: bool | None = None
