import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.common import ORMBase
from app.schemas.tour import NeighbourhoodRef

EventType = Literal["arrived", "audio_started", "audio_finished"]


class SessionCreate(BaseModel):
    tour_id: uuid.UUID


class TourSessionOut(ORMBase):
    id: uuid.UUID
    tour_id: uuid.UUID
    stops_visited: int
    completed: bool
    is_resumable: bool
    started_at: datetime
    completed_at: datetime | None


class SessionEventIn(BaseModel):
    client_event_id: uuid.UUID
    stop_id: uuid.UUID
    event_type: EventType
    occurred_at: datetime


class SessionEventBatchRequest(BaseModel):
    events: list[SessionEventIn]


class SessionEventBatchResponse(BaseModel):
    accepted: int
    duplicate: int
    session: TourSessionOut


class SessionSummary(BaseModel):
    """The "Walk complete" screen."""

    session_id: uuid.UUID
    tour_id: uuid.UUID
    tour_name: str
    completed: bool
    completed_at: datetime | None
    stops_visited: int
    stop_count: int
    distance_km: float | None
    duration_min: int | None
    neighbourhood: NeighbourhoodRef | None = None
    stamp_earned: bool = False  # first completed walk in this neighbourhood
    avg_rating: float | None = None
    rating_count: int = 0
    my_rating: int | None = None
    liked: bool = False
    commented: bool = False
