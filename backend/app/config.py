from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
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

    # Signed URL expiry for tour audio package downloads (seconds)
    SIGNED_URL_EXPIRE_SECONDS: int = 3600

    # Media URL signing — HMAC key used to sign audio download URLs.
    # Defaults to SECRET_KEY when not set. Set explicitly in production
    # to rotate media keys independently of auth tokens.
    MEDIA_SIGNING_KEY: str | None = None

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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()