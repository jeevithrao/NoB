import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.common import ORMBase


class NotificationOut(ORMBase):
    id: uuid.UUID
    type: Literal["reminder", "confirmed", "new", "review"]
    title: str
    subtitle: str | None
    tour_id: uuid.UUID | None
    is_read: bool
    created_at: datetime


class NotificationList(BaseModel):
    unread_count: int  # across ALL notifications, not just this page (drives the bell dot)
    items: list[NotificationOut]
