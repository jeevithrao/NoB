import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.text import clean_text
from app.schemas.common import ORMBase


class SavedTourCreate(BaseModel):
    tour_id: uuid.UUID


class SavedTourOut(ORMBase):
    tour_id: uuid.UUID
    saved_at: datetime


class CommentCreate(BaseModel):
    comment_text: str = Field(min_length=1, max_length=1000)

    @field_validator("comment_text")
    @classmethod
    def _sanitise(cls, value: str) -> str:
        cleaned = clean_text(value)
        if not cleaned:
            raise ValueError("Comment cannot be empty.")
        return cleaned


class CommentOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_name: str | None
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LikeStatus(BaseModel):
    liked: bool
    like_count: int


class RatingIn(BaseModel):
    rating: int = Field(ge=1, le=5)


class RatingSummary(BaseModel):
    avg_rating: float | None
    rating_count: int
    my_rating: int | None = None
    distribution: dict[int, int]  # {1: n, 2: n, ... 5: n}


class ReviewOut(BaseModel):
    """One card of "What walkers say"."""

    id: uuid.UUID
    tour_id: uuid.UUID
    tour_name: str
    user_name: str  # first name + last initial
    rating: int | None
    content: str
    created_at: datetime
