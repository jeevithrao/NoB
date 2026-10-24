from sqlalchemy import BigInteger, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RateLimitHit(Base):
    """Fixed-window counters shared by every API worker/container (RATE_LIMIT_BACKEND=postgres).

    One row per (key, window). Rows older than an hour are deleted opportunistically.
    """

    __tablename__ = "rate_limit_hits"
    __table_args__ = (Index("ix_rate_limit_hits_window", "window_start"),)

    key: Mapped[str] = mapped_column(String(300), primary_key=True)
    window_start: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
