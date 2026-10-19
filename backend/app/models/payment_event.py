import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PaymentEvent(Base):
    """Every gateway webhook we accept, stored once.

    `event_id` (the gateway's unique delivery id) is UNIQUE, so a redelivered
    webhook is detected by the database itself: the idempotency guarantee from
    the NFR doc ("a retried webhook must not double-credit a purchase")."""

    __tablename__ = "payment_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    gateway_order_id: Mapped[str | None] = mapped_column(String(255), index=True)
    gateway_payment_id: Mapped[str | None] = mapped_column(String(255))
    outcome: Mapped[str] = mapped_column(String(50), nullable=False, default="received")
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
