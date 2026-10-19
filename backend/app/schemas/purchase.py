import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMBase


class PurchaseCreate(BaseModel):
    tour_id: uuid.UUID


class PurchaseOut(ORMBase):
    id: uuid.UUID
    tour_id: uuid.UUID
    status: str
    amount_paise: int
    is_locked: bool
    gateway_order_id: str | None
    created_at: datetime


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


class CheckoutVerifyRequest(BaseModel):
    """The three values Razorpay Checkout hands back to the app on success."""

    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
