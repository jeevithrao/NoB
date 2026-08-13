"""Authentication router.

Endpoints:
  POST /auth/signup          — email/password registration
  POST /auth/login           — email/password login
  POST /auth/google          — Google Sign-In (Phase 2)
  POST /auth/request-otp     — request a 6-digit email OTP (Phase 2)
  POST /auth/verify-otp      — verify OTP and get tokens (Phase 2)
  POST /auth/refresh         — silent token refresh
  POST /auth/logout          — invalidate session
  GET  /auth/me              — current user profile
"""
import random
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.dependencies import get_current_user
from app.models import OtpRequest, User, UserLoginSession
from app.schemas.auth import (
    GoogleSignInRequest,
    LoginRequest,
    OtpRequestBody,
    OtpVerifyRequest,
    RefreshRequest,
    SignupRequest,
    TokenResponse,
)
from app.schemas.user import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

# How long a generated OTP stays valid
_OTP_TTL_SECONDS = 600  # 10 minutes
# Maximum wrong attempts before the OTP record is locked
_OTP_MAX_ATTEMPTS = 5


def _api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


async def _issue_tokens(db: AsyncSession, user: User, device_identifier: str) -> TokenResponse:
    """Create a new login session for this device and invalidate every other
    active session on the account — this is the single-active-session rule
    from the Business Rules doc (logging in elsewhere kicks the old one out)."""
    await db.execute(
        update(UserLoginSession)
        .where(UserLoginSession.user_id == user.id, UserLoginSession.is_active.is_(True))
        .values(is_active=False)
    )

    login_session = UserLoginSession(
        user_id=user.id,
        device_id=device_identifier,
        refresh_token="pending",  # placeholder, replaced below once we know the session id
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(login_session)
    await db.flush()  # assigns login_session.id without ending the transaction

    refresh_token = create_refresh_token(user.id, login_session.id)
    login_session.refresh_token = refresh_token
    access_token = create_access_token(user.id, login_session.id, user.role)

    await db.commit()
    await db.refresh(user)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserOut.model_validate(user),
    )


# ---------------------------------------------------------------------------
# Email / password
# ---------------------------------------------------------------------------

@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise _api_error(status.HTTP_409_CONFLICT, "EMAIL_TAKEN", "An account with this email already exists.")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role="user",
    )
    db.add(user)
    await db.flush()
    return await _issue_tokens(db, user, body.device_identifier)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise _api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS", "Incorrect email or password.")

    return await _issue_tokens(db, user, body.device_identifier)


# ---------------------------------------------------------------------------
# Google Sign-In (Phase 2)
# ---------------------------------------------------------------------------

@router.post("/google", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def google_sign_in(body: GoogleSignInRequest, db: AsyncSession = Depends(get_db)):
    """Verify a Google id_token, then get-or-create the user and issue tokens.

    Requires the google-auth package (pip install google-auth).
    If GOOGLE_CLIENT_ID is not configured, returns 501 so tests can skip
    this path cleanly without a real Google project.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise _api_error(
            status.HTTP_501_NOT_IMPLEMENTED,
            "GOOGLE_NOT_CONFIGURED",
            "GOOGLE_CLIENT_ID is not set. Configure it to enable Google Sign-In.",
        )

    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests

        id_info = google_id_token.verify_oauth2_token(
            body.id_token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except Exception as exc:
        raise _api_error(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_GOOGLE_TOKEN",
            f"Could not verify Google token: {exc}",
        )

    email = id_info.get("email")
    if not email or not id_info.get("email_verified", False):
        raise _api_error(
            status.HTTP_401_UNAUTHORIZED,
            "GOOGLE_EMAIL_NOT_VERIFIED",
            "Google account email is not verified.",
        )

    # Get or create user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(uuid.uuid4().hex),  # unusable random password
            full_name=id_info.get("name"),
            role="user",
        )
        db.add(user)
        await db.flush()

    return await _issue_tokens(db, user, body.device_identifier)


# ---------------------------------------------------------------------------
# OTP flow (Phase 2)
# ---------------------------------------------------------------------------

@router.post("/request-otp", status_code=status.HTTP_200_OK)
async def request_otp(body: OtpRequestBody, db: AsyncSession = Depends(get_db)):
    """Generate a 6-digit OTP for the given email and store its hash.

    The raw code is not stored — only a SHA-256 hash so a DB leak doesn't
    expose valid codes. In production, wire up an email/SMS provider here
    (Twilio, SendGrid, etc.). For now the OTP is returned in the response
    body so the integration tests can verify end-to-end without real delivery.
    """
    raw_otp = f"{random.randint(0, 999999):06d}"
    otp_record = OtpRequest(
        email=body.email,
        otp_hash=OtpRequest.hash_otp(raw_otp),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=_OTP_TTL_SECONDS),
    )
    db.add(otp_record)
    await db.commit()

    # TODO: send raw_otp via email/SMS to body.email
    # For now, return it in the response (remove before production)
    return {
        "message": "OTP sent to your email.",
        # ↓ remove this line once real delivery is wired up
        "_dev_otp": raw_otp,
    }


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(body: OtpVerifyRequest, db: AsyncSession = Depends(get_db)):
    """Verify the OTP and issue tokens.

    Rate-limiting:
      - 5 wrong attempts on the same OTP record → 429 TOO_MANY_ATTEMPTS.
    Expiry:
      - OTP older than _OTP_TTL_SECONDS → 400 OTP_EXPIRED.
    Success path:
      - Marks the record used=True, get-or-creates the user, issues tokens.
    """
    now = datetime.now(timezone.utc)

    # Find the newest unused OTP for this email that hasn't been exhausted
    result = await db.execute(
        select(OtpRequest)
        .where(
            OtpRequest.email == body.email,
            OtpRequest.used.is_(False),
        )
        .order_by(OtpRequest.created_at.desc())
    )
    otp_record = result.scalars().first()

    if otp_record is None:
        raise _api_error(status.HTTP_400_BAD_REQUEST, "OTP_NOT_FOUND", "No pending OTP for this email. Request a new one.")

    # Check expiry first (clearer error than rate-limit when both apply)
    if now > otp_record.expires_at.replace(tzinfo=timezone.utc):
        raise _api_error(status.HTTP_400_BAD_REQUEST, "OTP_EXPIRED", "This OTP has expired. Request a new one.")

    # Rate-limit check
    if otp_record.attempt_count >= _OTP_MAX_ATTEMPTS:
        raise _api_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "TOO_MANY_ATTEMPTS",
            f"Too many incorrect attempts. Request a new OTP.",
        )

    # Verify the submitted code
    if OtpRequest.hash_otp(body.otp) != otp_record.otp_hash:
        otp_record.attempt_count += 1
        await db.commit()
        remaining = _OTP_MAX_ATTEMPTS - otp_record.attempt_count
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_OTP",
            f"Incorrect code. {remaining} attempt(s) remaining.",
        )

    # Success — mark as used
    otp_record.used = True
    await db.flush()

    # Get or create the user account for this email
    user_result = await db.execute(select(User).where(User.email == body.email))
    user = user_result.scalar_one_or_none()
    if user is None:
        user = User(
            email=body.email,
            password_hash=hash_password(uuid.uuid4().hex),  # unusable random password
            role="user",
        )
        db.add(user)
        await db.flush()

    return await _issue_tokens(db, user, body.device_identifier)


# ---------------------------------------------------------------------------
# Token refresh & session management
# ---------------------------------------------------------------------------

@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
    except jwt.ExpiredSignatureError:
        raise _api_error(status.HTTP_401_UNAUTHORIZED, "TOKEN_EXPIRED", "Refresh token expired, please log in again.")
    except jwt.InvalidTokenError:
        raise _api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_TOKEN", "Invalid refresh token.")

    if payload.get("type") != "refresh":
        raise _api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_TOKEN", "Wrong token type.")

    login_session_id = uuid.UUID(payload["sid"])
    result = await db.execute(select(UserLoginSession).where(UserLoginSession.id == login_session_id))
    login_session = result.scalar_one_or_none()
    if login_session is None or not login_session.is_active or login_session.refresh_token != body.refresh_token:
        raise _api_error(status.HTTP_401_UNAUTHORIZED, "SESSION_INVALIDATED", "This session is no longer active.")

    user_result = await db.execute(select(User).where(User.id == login_session.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise _api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_TOKEN", "User no longer exists.")

    access_token = create_access_token(user.id, login_session.id, user.role)
    login_session.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=body.refresh_token,
        user=UserOut.model_validate(user),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(UserLoginSession)
        .where(UserLoginSession.user_id == current_user.id, UserLoginSession.is_active.is_(True))
        .values(is_active=False)
    )
    await db.commit()


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
