import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Neighbourhood(Base):
    """An area of the city (Malleshwaram, Indiranagar...) that groups tours.
    Drives the "By neighbourhood" row, neighbourhood pages and passport stamps."""

    __tablename__ = "neighbourhoods"
    __table_args__ = (UniqueConstraint("name", "city", name="uq_neighbourhoods_name_city"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False, default="Bangalore")
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    cover_image: Mapped[str | None] = mapped_column(String(500))
    centroid_lat: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    centroid_lng: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tours: Mapped[list["Tour"]] = relationship(back_populates="neighbourhood")
