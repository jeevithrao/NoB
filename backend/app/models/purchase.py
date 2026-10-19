import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, CheckConstraint, DateTime, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Purchase(Base):
    __tablename__ = "purchases"
    __table_args__ = (
        # Partial unique index: only one active (pending or completed) purchase
        # per user-tour pair. Failed purchases are excluded, allowing retries
        # without hitting a unique constraint violation.
        Index(
            "idx_one_active_purchase_per_user_tour",
            "user_id",
            "tour_id",
            unique=True,
            postgresql_where="status IN ('pending', 'completed')",
        ),
        CheckConstraint(
            "status IN ('pending', 'completed', 'failed', 'refunded')", name="ck_purchases_status"
        ),
        CheckConstraint("amount_paise >= 0", name="ck_purchases_amount_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tour_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tours.id", ondelete="CASCADE"), nullable=False, index=True
    )
    gateway_order_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    gateway_payment_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    device_id: Mapped[str | None] = mapped_column(String(255))
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="purchases")
    tour: Mapped["Tour"] = relationship(back_populates="purchases")
    tour_sessions: Mapped[list["TourSession"]] = relationship(
        back_populates="purchase"
    )