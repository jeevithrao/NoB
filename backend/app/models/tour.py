import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Integer, Boolean, Numeric, DateTime, ForeignKey, Text, CheckConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID
from app.database import Base


class Tour(Base):
    __tablename__ = "tours"
    __table_args__ = (
        CheckConstraint("price_paise >= 0", name="ck_tours_price_non_negative"),
        CheckConstraint("difficulty IS NULL OR difficulty IN ('Easy', 'Moderate', 'Hard')", name="ck_tours_difficulty"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    neighbourhood_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("neighbourhoods.id", ondelete="SET NULL"), index=True
    )
    cover_image: Mapped[str | None] = mapped_column(String(500))
    duration_min: Mapped[int | None] = mapped_column(Integer)
    distance_km: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default=text("false"), index=True)
    # Content shown on the tour detail page
    gallery_images: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    includes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    languages: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    preview_audio_filename: Mapped[str | None] = mapped_column(String(500))
    preview_audio_title: Mapped[str | None] = mapped_column(String(255))
    # Presentation fields shown on the walk page / filters.
    theme: Mapped[str | None] = mapped_column(String(50), index=True)  # Heritage, Culture, Nature, Colonial...
    difficulty: Mapped[str | None] = mapped_column(String(20))  # Easy | Moderate | Hard
    start_point: Mapped[str | None] = mapped_column(String(255))  # meeting point, e.g. "Sampige Road Metro Gate"
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    price_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_free: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    neighbourhood: Mapped["Neighbourhood | None"] = relationship(back_populates="tours", lazy="joined")
    stops: Mapped[list["Stop"]] = relationship(
        back_populates="tour",
        order_by="Stop.order_index",
        cascade="all, delete-orphan"
    )
    purchases: Mapped[list["Purchase"]] = relationship(
        back_populates="tour", cascade="all, delete-orphan"
    )
    tour_sessions: Mapped[list["TourSession"]] = relationship(
        back_populates="tour", cascade="all, delete-orphan"
    )
    saved_by: Mapped[list["SavedTour"]] = relationship(
        back_populates="tour", cascade="all, delete-orphan"
    )
    likes: Mapped[list["TourLike"]] = relationship(
        back_populates="tour", cascade="all, delete-orphan"
    )
    comments: Mapped[list["TourComment"]] = relationship(
        back_populates="tour", cascade="all, delete-orphan"
    )