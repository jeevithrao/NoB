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
    reviews_count: int  # ratings the user has given


class PassportStamp(BaseModel):
    neighbourhood: NeighbourhoodRef
    cover_image: str | None
    emoji: str | None = None
    walk_name: str | None = None  # the first walk completed here (back of the stamp)
    tours_total: int
    tours_completed: int
    stamped: bool
    stamped_at: datetime | None  # when the first walk there was completed


class Passport(BaseModel):
    stamps_collected: int
    total_neighbourhoods: int
    stamps: list[PassportStamp]


# ---- profile, preferences, deletion ----

import re  # noqa: E402

from pydantic import Field, field_validator  # noqa: E402

from app.core.text import clean_text  # noqa: E402

_USERNAME = re.compile(r"^[a-z0-9_]{3,30}$")


class ProfileUpdate(BaseModel):
    """Only the fields sent are changed. `username: null` clears it."""

    full_name: str | None = Field(default=None, max_length=100)
    username: str | None = Field(default=None, max_length=31)

    @field_validator("full_name")
    @classmethod
    def _clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = clean_text(value)
        if not cleaned:
            raise ValueError("Name cannot be empty.")
        return cleaned

    @field_validator("username")
    @classmethod
    def _clean_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lstrip("@").lower()
        if not _USERNAME.match(value):
            raise ValueError("Username must be 3-30 characters: letters, numbers or underscores.")
        return value


class PreferencesUpdate(BaseModel):
    notifications_enabled: bool | None = None
    analytics_opt_in: bool | None = None
    marketing_opt_in: bool | None = None


class DeleteAccountRequest(BaseModel):
    confirm: str  # must be the word DELETE

    @field_validator("confirm")
    @classmethod
    def _must_confirm(cls, value: str) -> str:
        if value.strip() != "DELETE":
            raise ValueError('Type DELETE to confirm.')
        return value
