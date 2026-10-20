import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase

TourStatus = Literal["not_purchased", "purchased", "in_progress", "completed_locked"]


Difficulty = Literal["Easy", "Moderate", "Hard"]


class NeighbourhoodRef(ORMBase):
    id: uuid.UUID
    name: str
    slug: str
    emoji: str | None = None


class TourListItem(ORMBase):
    id: uuid.UUID
    name: str
    description: str | None
    city: str
    cover_image: str | None
    duration_min: int | None
    distance_km: float | None  # JSON number, not a Decimal string
    price_paise: int
    is_free: bool
    neighbourhood: NeighbourhoodRef | None = None
    is_featured: bool = False
    theme: str | None = None
    difficulty: Difficulty | None = None
    status: TourStatus = "not_purchased"
    like_count: int = 0
    avg_rating: float | None = None
    rating_count: int = 0


class StopPreview(ORMBase):
    """What anyone may see of a stop before buying: no narration, audio or coordinates."""

    order_index: int
    name: str
    blurb: str | None = None
    icon: str | None = None


class TourDetail(TourListItem):
    is_published: bool
    stop_count: int = 0
    purchase_id: uuid.UUID | None = None
    gallery_images: list[str] = []
    includes: list[str] = []
    languages: list[str] = []
    # Short promotional sample (time-limited signed URL); visible before purchase.
    preview_audio_url: str | None = None
    preview_audio_title: str | None = None
    start_point: str | None = None
    tags: list[str] = []
    neighbourhood_description: str | None = None
    stops_preview: list[StopPreview] = []
    my_rating: int | None = None
    liked_by_me: bool = False


class StopOut(ORMBase):
    id: uuid.UUID
    order_index: int
    name: str
    narrative_text: str | None
    lat: float
    lng: float
    trigger_radius_m: int
    blurb: str | None = None
    icon: str | None = None


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
    blurb: str | None = Field(default=None, max_length=255)
    icon: str | None = Field(default=None, max_length=16)


class TourCreate(BaseModel):
    name: str
    description: str | None = None
    city: str = "Bangalore"
    cover_image: str | None = None
    duration_min: int | None = None
    distance_km: Decimal | None = None
    price_paise: int = Field(default=0, ge=0)
    is_free: bool = False
    neighbourhood_id: uuid.UUID | None = None
    is_featured: bool = False
    gallery_images: list[str] = []
    includes: list[str] = []
    languages: list[str] = []
    preview_audio_filename: str | None = None
    preview_audio_title: str | None = Field(default=None, max_length=255)
    theme: str | None = Field(default=None, max_length=50)
    difficulty: Difficulty | None = None
    start_point: str | None = Field(default=None, max_length=255)
    tags: list[str] = []


class TourUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    city: str | None = None
    cover_image: str | None = None
    duration_min: int | None = None
    distance_km: Decimal | None = None
    price_paise: int | None = Field(default=None, ge=0)
    is_free: bool | None = None
    neighbourhood_id: uuid.UUID | None = None
    is_featured: bool | None = None
    gallery_images: list[str] | None = None
    includes: list[str] | None = None
    languages: list[str] | None = None
    preview_audio_filename: str | None = None
    preview_audio_title: str | None = Field(default=None, max_length=255)
    theme: str | None = Field(default=None, max_length=50)
    difficulty: Difficulty | None = None
    start_point: str | None = Field(default=None, max_length=255)
    tags: list[str] | None = None
