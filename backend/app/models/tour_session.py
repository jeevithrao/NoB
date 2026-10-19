import uuid
from datetime import datetime
from sqlalchemy import Integer, Boolean, CheckConstraint, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class TourSession(Base):
    __tablename__ = "tour_sessions"
    __table_args__ = (
        # Licence rule (Business Rules §1): a (user, tour) pair can have at most
        # ONE completed session, ever. The database refuses a second one even if
        # application logic has a bug or two requests race.
        Index(
            "idx_one_completed_session_per_user_tour",
            "user_id",
            "tour_id",
            unique=True,
            postgresql_where="completed = true",
        ),
        CheckConstraint("stops_visited >= 0", name="ck_tour_sessions_stops_visited_non_negative"),
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
    purchase_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchases.id", ondelete="SET NULL"), index=True
    )
    stops_visited: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_resumable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    user: Mapped["User"] = relationship(back_populates="tour_sessions")
    tour: Mapped["Tour"] = relationship(back_populates="tour_sessions")
    purchase: Mapped["Purchase"] = relationship(back_populates="tour_sessions")
    session_events: Mapped[list["SessionEvent"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )