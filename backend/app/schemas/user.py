import uuid
from datetime import datetime

from app.schemas.common import ORMBase


class UserOut(ORMBase):
    id: uuid.UUID
    email: str
    full_name: str | None
    avatar_url: str | None
    username: str | None = None
    role: str
    notifications_enabled: bool = True
    analytics_opt_in: bool = False
    marketing_opt_in: bool = False
    created_at: datetime
