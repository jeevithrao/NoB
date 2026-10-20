import hashlib
import hmac
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.config import settings
from app.database import Base


class OtpRequest(Base):
    """Stores a hashed one-time password for email-based authentication.

    Design notes:
    - The raw OTP is never stored; only a keyed HMAC-SHA256 (bound to the
      email, key = SECRET_KEY) so a DB leak can't be brute-forced offline the
      way a bare hash of a 6-digit code could.
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
    # What the code is for: a code issued for one purpose never works for another.
    purpose: Mapped[str] = mapped_column(String(20), nullable=False, default="login", server_default="login")
    # HMAC-SHA256 hex digest of "<email>:<code>"
    otp_hash: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    @staticmethod
    def hash_otp(email: str, otp: str, purpose: str = "login") -> str:
        """Keyed one-way hash of the code, bound to the (lower-cased) email and the purpose."""
        prefix = "" if purpose == "login" else f"{purpose}:"
        message = f"{prefix}{email.strip().lower()}:{otp}".encode()
        return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()
