import uuid
from datetime import datetime

from app.schemas.common import ORMBase


class UserOut(ORMBase):
    id: uuid.UUID
    email: str
    full_name: str | None
    avatar_url: str | None
    role: str
    created_at: datetime
