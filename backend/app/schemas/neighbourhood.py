import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase
from app.schemas.tour import TourListItem


class NeighbourhoodOut(ORMBase):
    id: uuid.UUID
    name: str
    slug: str
    city: str
    description: str | None
    cover_image: str | None
    tagline: str | None = None
    emoji: str | None = None
    centroid_lat: float | None
    centroid_lng: float | None
    tour_count: int = 0


class NeighbourhoodDetail(NeighbourhoodOut):
    tours: list[TourListItem] = []


class NeighbourhoodCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    city: str = "Bangalore"
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)
    description: str | None = None
    cover_image: str | None = None
    tagline: str | None = Field(default=None, max_length=255)
    emoji: str | None = Field(default=None, max_length=16)
    centroid_lat: Decimal | None = None
    centroid_lng: Decimal | None = None


class NeighbourhoodUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    cover_image: str | None = None
    centroid_lat: Decimal | None = None
    centroid_lng: Decimal | None = None
    tagline: str | None = Field(default=None, max_length=255)
    emoji: str | None = Field(default=None, max_length=16)
