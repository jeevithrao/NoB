import uuid
import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(user_id: uuid.UUID, login_session_id: uuid.UUID, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "sid": str(login_session_id),
        "role": role,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: uuid.UUID, login_session_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "sid": str(login_session_id),
        "exp": expire,
        "type": "refresh",
        # jti makes every refresh token unique even if issued in the same second,
        # since the DB column has a UNIQUE constraint on refresh_token.
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


# ---------------------------------------------------------------------------
# Media URL signing — HMAC-SHA256 time-limited query strings for audio files.
# ---------------------------------------------------------------------------

def sign_media_path(path: str, expires_in: int) -> str:
    """Returns a query string ?exp=<unix_ts>&sig=<hmac_sha256_hex>.

    The signed URL is valid for `expires_in` seconds from now. Include it in
    the audio URL returned by _signed_audio_url() so that downloaded packages
    can't be shared indefinitely as plain static links.
    """
    exp = int(time.time()) + expires_in
    raw = f"{path}:{exp}"
    sig = hmac.new(
        settings.media_signing_key.encode(),
        raw.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"?exp={exp}&sig={sig}"


def verify_media_signature(path: str, exp: str, sig: str) -> bool:
    """Returns True only if the HMAC signature is valid and not yet expired."""
    try:
        exp_int = int(exp)
    except ValueError:
        return False
    if time.time() > exp_int:
        return False
    raw = f"{path}:{exp_int}"
    expected = hmac.new(
        settings.media_signing_key.encode(),
        raw.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, sig)
