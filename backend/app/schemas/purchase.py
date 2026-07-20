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
    """gateway_config is a placeholder blob the client hands to the Razorpay/
    Stripe SDK. While MOCK_PAYMENTS=True it's empty and the purchase completes
    immediately server-side instead."""


class BindDeviceRequest(BaseModel):
    device_identifier: str


class PaymentWebhookPayload(BaseModel):
    """Shape of what a real gateway would POST. Kept intentionally loose since
    the real provider isn't wired up yet — validated more strictly once a
    provider is chosen."""

    gateway_order_id: str
    gateway_payment_id: str
    status: str
    signature: str | None = None
