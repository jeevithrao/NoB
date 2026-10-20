"""One-time email codes, shared by sign-in and password reset.

A code is bound to an email AND a purpose, stored only as a keyed hash, single-use,
time-limited and attempt-limited. Callers decide whether to actually send the email;
issuing always records a row, so rate limits behave identically for accounts that do
and don't exist (no account enumeration).
"""
from __future__ import annotations

import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import OtpRequest


class OtpError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code, self.code, self.message = status_code, code, message


async def issue_code(db: AsyncSession, email: str, purpose: str) -> str:
    """Create a fresh code (invalidating older unused ones) and return it. Commits."""
    email = email.strip().lower()
    now = datetime.now(timezone.utc)
    ttl = timedelta(seconds=settings.OTP_TTL_SECONDS)
    recent = (
        await db.execute(
            select(func.count(OtpRequest.id)).where(
                OtpRequest.email == email, OtpRequest.purpose == purpose, OtpRequest.created_at > now - ttl
            )
        )
    ).scalar_one()
    if recent >= settings.OTP_MAX_REQUESTS_PER_WINDOW:
        raise OtpError(
            429, "OTP_REQUEST_LIMIT", "Too many codes requested. Please wait a few minutes before asking for another."
        )
    await db.execute(
        update(OtpRequest)
        .where(OtpRequest.email == email, OtpRequest.purpose == purpose, OtpRequest.used.is_(False))
        .values(used=True)
    )
    raw = f"{secrets.randbelow(1_000_000):06d}"
    db.add(
        OtpRequest(email=email, purpose=purpose, otp_hash=OtpRequest.hash_otp(email, raw, purpose), expires_at=now + ttl)
    )
    await db.commit()
    return raw


async def consume_code(db: AsyncSession, email: str, code: str, purpose: str) -> None:
    """Check the newest unused code for this email+purpose and mark it used.
    Raises OtpError (wrong / expired / locked). Wrong guesses are committed."""
    email = email.strip().lower()
    now = datetime.now(timezone.utc)
    record = (
        await db.execute(
            select(OtpRequest)
            .where(OtpRequest.email == email, OtpRequest.purpose == purpose, OtpRequest.used.is_(False))
            .order_by(OtpRequest.created_at.desc())
        )
    ).scalars().first()

    if record is None:
        raise OtpError(400, "OTP_NOT_FOUND", "No pending code for this email. Request a new one.")
    if now > record.expires_at:
        raise OtpError(400, "OTP_EXPIRED", "This code has expired. Request a new one.")
    if record.attempt_count >= settings.OTP_MAX_ATTEMPTS:
        raise OtpError(429, "TOO_MANY_ATTEMPTS", "Too many incorrect attempts. Request a new code.")

    if not hmac.compare_digest(OtpRequest.hash_otp(email, code, purpose), record.otp_hash):
        record.attempt_count += 1
        await db.commit()
        remaining = settings.OTP_MAX_ATTEMPTS - record.attempt_count
        raise OtpError(400, "INVALID_OTP", f"Incorrect code. {remaining} attempt(s) remaining.")

    record.used = True
    await db.flush()
