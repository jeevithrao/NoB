"""Outgoing email (OTP delivery).

Backends are chosen by settings.EMAIL_BACKEND:
  console  log the message (development only)
  smtp     real delivery over SMTP
  memory   keep messages in an in-process outbox (used by tests)
"""
from __future__ import annotations

import asyncio
import logging
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage as MimeMessage
from typing import Protocol

from app.config import settings

logger = logging.getLogger("nob.email")


@dataclass
class OutgoingEmail:
    to: str
    subject: str
    body: str


class EmailBackend(Protocol):
    async def send(self, message: OutgoingEmail) -> None: ...


class ConsoleBackend:
    async def send(self, message: OutgoingEmail) -> None:
        logger.warning("EMAIL (console backend) to=%s subject=%s\n%s", message.to, message.subject, message.body)


@dataclass
class MemoryBackend:
    outbox: list[OutgoingEmail] = field(default_factory=list)

    async def send(self, message: OutgoingEmail) -> None:
        self.outbox.append(message)


class SmtpBackend:
    async def send(self, message: OutgoingEmail) -> None:
        if not settings.SMTP_HOST:
            raise RuntimeError("SMTP_HOST is not configured")
        await asyncio.to_thread(self._send_sync, message)

    @staticmethod
    def _send_sync(message: OutgoingEmail) -> None:
        mime = MimeMessage()
        mime["From"] = settings.EMAIL_FROM
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.body)
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD or "")
            smtp.send_message(mime)


_backend: EmailBackend | None = None


def get_email_backend() -> EmailBackend:
    global _backend
    if _backend is None:
        choice = settings.EMAIL_BACKEND
        if choice == "smtp":
            _backend = SmtpBackend()
        elif choice == "memory":
            _backend = MemoryBackend()
        else:
            _backend = ConsoleBackend()
    return _backend


def set_email_backend(backend: EmailBackend | None) -> None:
    """Swap the backend (tests) or pass None to re-read settings."""
    global _backend
    _backend = backend


async def send_otp_email(to: str, code: str, ttl_minutes: int) -> None:
    await get_email_backend().send(
        OutgoingEmail(
            to=to,
            subject="Your NoB sign-in code",
            body=(
                f"Your Neighbourhoods of Bangalore code is {code}.\n"
                f"It expires in {ttl_minutes} minutes. If you didn't ask for it, ignore this email."
            ),
        )
    )


async def send_password_reset_email(to: str, code: str, ttl_minutes: int) -> None:
    await get_email_backend().send(
        OutgoingEmail(
            to=to,
            subject="Reset your NoB password",
            body=(
                f"Your Neighbourhoods of Bangalore password reset code is {code}.\n"
                f"It expires in {ttl_minutes} minutes. If you didn't ask for it, you can ignore this email: your password has not changed."
            ),
        )
    )
