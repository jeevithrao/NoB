import uuid
from datetime import datetime

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase
from app.schemas.tour import NeighbourhoodRef


class PurchaseCreate(BaseModel):
    tour_id: uuid.UUID


class PurchaseOut(ORMBase):
    id: uuid.UUID
    booking_ref: str
    tour_id: uuid.UUID
    status: str
    amount_paise: int
    is_locked: bool
    gateway_order_id: str | None
    created_at: datetime


class BookingTour(ORMBase):
    id: uuid.UUID
    name: str
    cover_image: str | None
    duration_min: int | None
    distance_km: float | None = None
    theme: str | None = None
    neighbourhood: NeighbourhoodRef | None = None


class BookingOut(BaseModel):
    """One row of "My Bookings"."""

    purchase_id: uuid.UUID
    booking_ref: str
    status: Literal["completed", "refunded"]
    amount_paise: int
    purchased_at: datetime
    tour: BookingTour
    walk_status: Literal["not_started", "in_progress", "completed"]
    stops_visited: int
    stop_count: int
    session_id: uuid.UUID | None = None
    completed_at: datetime | None = None
    my_rating: int | None = None  # None = not reviewed yet
    device_bound: bool
    device_status: Literal["unbound", "this_device", "other_device"]
    rebind_available_at: datetime | None = None  # set while the move cooldown is running
    can_refund: bool
    refund_deadline: datetime | None = None


class PurchaseCreateResponse(BaseModel):
    purchase_id: uuid.UUID
    status: str
    gateway_order_id: str | None
    gateway_config: dict
    """gateway_config is what the client hands to the Razorpay Checkout SDK
    (key_id, order_id, amount, currency, name). While MOCK_PAYMENTS=true it is
    {"mock": true} and the purchase is already completed."""


class BindDeviceRequest(BaseModel):
    device_identifier: str


class RebindDeviceRequest(BaseModel):
    device_identifier: str = Field(min_length=1, max_length=255)


class CheckoutVerifyRequest(BaseModel):
    """The three values Razorpay Checkout hands back to the app on success."""

    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
