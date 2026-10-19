import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import CheckConstraint, String, Integer, Numeric, DateTime, Text, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Stop(Base):
    __tablename__ = "stops"
    __table_args__ = (
        UniqueConstraint("tour_id", "order_index"),
        CheckConstraint("trigger_radius_m > 0", name="ck_stops_trigger_radius_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tour_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tours.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    narrative_text: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    lng: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    trigger_radius_m: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    audio_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    tour: Mapped["Tour"] = relationship(back_populates="stops")
    session_events: Mapped[list["SessionEvent"]] = relationship(
        back_populates="stop", cascade="all, delete-orphan"
    )