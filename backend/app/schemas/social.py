import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase


class SavedTourCreate(BaseModel):
    tour_id: uuid.UUID


class SavedTourOut(ORMBase):
    tour_id: uuid.UUID
    saved_at: datetime


class CommentCreate(BaseModel):
    comment_text: str = Field(min_length=1, max_length=2000)


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
