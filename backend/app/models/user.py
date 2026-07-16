import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    login_sessions: Mapped[list["UserLoginSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    purchases: Mapped[list["Purchase"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    tour_sessions: Mapped[list["TourSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    saved_tours: Mapped[list["SavedTour"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    likes: Mapped[list["TourLike"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    comments: Mapped[list["TourComment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )