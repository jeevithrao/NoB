import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.tour import NeighbourhoodRef


class ProfileStats(BaseModel):
    walks_completed: int
    distance_km: float
    stops_visited: int
    listening_minutes: int
    neighbourhoods_stamped: int


class PassportStamp(BaseModel):
    neighbourhood: NeighbourhoodRef
    cover_image: str | None
    tours_total: int
    tours_completed: int
    stamped: bool
    stamped_at: datetime | None  # when the first walk there was completed


class Passport(BaseModel):
    stamps_collected: int
    total_neighbourhoods: int
    stamps: list[PassportStamp]
