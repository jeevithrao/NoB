from functools import lru_cache
from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings

_PLACEHOLDER_SECRET_MARKERS = ("change-this", "changeme", "change_me", "your-secret")


class Settings(BaseSettings):
    # Runtime environment: "development" | "staging" | "production".
    # Anything other than "development" turns on strict startup checks (see
    # _validate_for_environment) so dev-only shortcuts can never ship.
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str
    DATABASE_URL_SYNC: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # File storage
    AUDIO_DIR: str = "./media/audio"
    IMAGE_DIR: str = "./media/images"
    BASE_URL: str = "http://localhost:8000"

    # Payments
    # When True, /purchases auto-completes immediately instead of talking to a
    # real gateway — lets us build/test the whole purchase -> download -> walk
    # flow before Razorpay/Stripe keys exist.
    MOCK_PAYMENTS: bool = True
    RAZORPAY_KEY_ID: str | None = None
    RAZORPAY_KEY_SECRET: str | None = None
    RAZORPAY_WEBHOOK_SECRET: str | None = None
    RAZORPAY_API_BASE: str = "https://api.razorpay.com/v1"
    PAYMENT_CURRENCY: str = "INR"
    PAYMENT_MERCHANT_NAME: str = "Neighbourhoods of Bangalore"
    GOOGLE_CLIENT_ID: str | None = None

    # Signed URL expiry for tour audio package downloads (seconds)
    SIGNED_URL_EXPIRE_SECONDS: int = 3600

    # Media URL signing — HMAC key used to sign audio download URLs.
    # Defaults to SECRET_KEY when not set. Set explicitly in production
    # to rotate media keys independently of auth tokens.
    MEDIA_SIGNING_KEY: str | None = None

    # Email (OTP delivery). "console" logs the message (dev only), "smtp" sends
    # real mail, "memory" keeps messages in-process (used by the test-suite).
    EMAIL_BACKEND: str = "console"
    EMAIL_FROM: str = "NoB <no-reply@nob.app>"
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_USE_TLS: bool = True

    # OTP policy
    OTP_TTL_SECONDS: int = 600
    OTP_MAX_ATTEMPTS: int = 5
    OTP_MAX_REQUESTS_PER_WINDOW: int = 3  # per email, per OTP_TTL_SECONDS
    # Development convenience ONLY: echo the OTP in the /auth/request-otp
    # response. Ignored (and rejected at startup) outside development.
    EXPOSE_DEV_OTP: bool = False

    # Rate limits (per client IP and per account, sliding 60s window).
    # In-memory, so counts are per-process; fine for a single API container.
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10

    # Admin bootstrap used by `python -m app.seed` (never hardcode these).
    ADMIN_EMAIL: str = "admin@nob.app"
    ADMIN_PASSWORD: str | None = None

    # Debug — gates SQLAlchemy query logging (echo=True exposes passwords
    # and JWTs in logs when not in development).
    DEBUG: bool = False

    # CORS — comma-separated list of allowed origins.
    # Never use "*" with allow_credentials=True.
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://localhost:8081"

    @property
    def media_signing_key(self) -> str:
        return self.MEDIA_SIGNING_KEY or self.SECRET_KEY

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def _validate_for_environment(self) -> "Settings":
        if not self.MOCK_PAYMENTS and not (
            self.RAZORPAY_KEY_ID and self.RAZORPAY_KEY_SECRET and self.RAZORPAY_WEBHOOK_SECRET
        ):
            raise ValueError(
                "MOCK_PAYMENTS=false requires RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET and RAZORPAY_WEBHOOK_SECRET"
            )
        if self.ENVIRONMENT == "development":
            return self
        problems: list[str] = []
        key = self.SECRET_KEY.lower()
        if len(self.SECRET_KEY) < 32 or any(m in key for m in _PLACEHOLDER_SECRET_MARKERS):
            problems.append("SECRET_KEY must be a random value of at least 32 characters")
        if self.EXPOSE_DEV_OTP:
            problems.append("EXPOSE_DEV_OTP must be false")
        if self.EMAIL_BACKEND != "smtp":
            problems.append("EMAIL_BACKEND must be 'smtp'")
        if self.MOCK_PAYMENTS:
            problems.append("MOCK_PAYMENTS must be false")
        if self.DEBUG:
            problems.append("DEBUG must be false")
        if problems:
            raise ValueError(
                f"Unsafe configuration for ENVIRONMENT={self.ENVIRONMENT}: " + "; ".join(problems)
            )
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()