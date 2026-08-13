import uuid
import hashlib
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class OtpRequest(Base):
    """Stores a hashed one-time password for email-based authentication.

    Design notes:
    - The raw OTP is never stored; only a SHA-256 hash so a DB leak doesn't
      expose valid codes.
    - attempt_count prevents brute-force: 5 wrong guesses locks the record.
    - used=True after a successful verification prevents replay.
    - Multiple pending rows per email are allowed; only the newest valid one
      should be used.
    """
    __tablename__ = "otp_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # SHA-256 hex digest of the 6-digit code
    otp_hash: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    @staticmethod
    def hash_otp(otp: str) -> str:
        """One-way SHA-256 hash of the raw OTP string."""
        return hashlib.sha256(otp.encode()).hexdigest()
