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
import hmac
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.rate_limit import client_ip, limiter
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
from app.services.email import send_otp_email

router = APIRouter(prefix="/auth", tags=["auth"])

logger = logging.getLogger("nob.auth")


def _api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


def _throttle(request: Request, scope: str, account: str | None = None) -> None:
    """Rate-limit by client IP and (when known) by account, so credential
    stuffing from one IP *and* a distributed attack on one account are both
    slowed down."""
    limit = settings.RATE_LIMIT_AUTH_PER_MINUTE
    limiter.hit(f"{scope}:ip:{client_ip(request)}", limit)
    if account:
        limiter.hit(f"{scope}:acct:{account.strip().lower()}", limit)


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
async def signup(body: SignupRequest, request: Request, db: AsyncSession = Depends(get_db)):
    email = body.email.strip().lower()
    _throttle(request, "signup", email)
    existing = await db.execute(select(User).where(func.lower(User.email) == email))
    if existing.scalar_one_or_none() is not None:
        raise _api_error(status.HTTP_409_CONFLICT, "EMAIL_TAKEN", "An account with this email already exists.")

    user = User(
        email=email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role="user",
    )
    db.add(user)
    await db.flush()
    return await _issue_tokens(db, user, body.device_identifier)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    email = body.email.strip().lower()
    _throttle(request, "login", email)
    result = await db.execute(select(User).where(func.lower(User.email) == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise _api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS", "Incorrect email or password.")

    return await _issue_tokens(db, user, body.device_identifier)


# ---------------------------------------------------------------------------
# Google Sign-In (Phase 2)
# ---------------------------------------------------------------------------

@router.post("/google", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def google_sign_in(body: GoogleSignInRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Verify a Google id_token, then get-or-create the user and issue tokens.

    Requires the google-auth package (pip install google-auth).
    If GOOGLE_CLIENT_ID is not configured, returns 501 so tests can skip
    this path cleanly without a real Google project.
    """
    _throttle(request, "google")
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
    except Exception:
        # Log the reason server-side; never echo verifier internals to the client.
        logger.warning("Google id_token verification failed", exc_info=True)
        raise _api_error(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_GOOGLE_TOKEN",
            "Could not verify the Google sign-in. Please try again.",
        )

    email = id_info.get("email")
    if not email or not id_info.get("email_verified", False):
        raise _api_error(
            status.HTTP_401_UNAUTHORIZED,
            "GOOGLE_EMAIL_NOT_VERIFIED",
            "Google account email is not verified.",
        )

    # Get or create user
    email = email.strip().lower()
    result = await db.execute(select(User).where(func.lower(User.email) == email))
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
async def request_otp(body: OtpRequestBody, request: Request, db: AsyncSession = Depends(get_db)):
    """Email a 6-digit one-time code to the address.

    Security properties:
      - the code is delivered ONLY by email; it is never in the response
        (unless ENVIRONMENT=development and EXPOSE_DEV_OTP=true);
      - generated with `secrets`, stored only as a keyed hash;
      - the response is identical whether or not an account exists;
      - at most OTP_MAX_REQUESTS_PER_WINDOW codes per email per TTL window,
        and a new code invalidates any older unused one.
    """
    email = body.email.strip().lower()
    _throttle(request, "otp-request", email)
    now = datetime.now(timezone.utc)
    ttl = timedelta(seconds=settings.OTP_TTL_SECONDS)

    recent = await db.execute(
        select(func.count(OtpRequest.id)).where(
            OtpRequest.email == email, OtpRequest.created_at > now - ttl
        )
    )
    if recent.scalar_one() >= settings.OTP_MAX_REQUESTS_PER_WINDOW:
        raise _api_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "OTP_REQUEST_LIMIT",
            "Too many codes requested. Please wait a few minutes before asking for another.",
        )

    # Only the newest code is ever valid.
    await db.execute(
        update(OtpRequest).where(OtpRequest.email == email, OtpRequest.used.is_(False)).values(used=True)
    )

    raw_otp = f"{secrets.randbelow(1_000_000):06d}"
    db.add(
        OtpRequest(
            email=email,
            otp_hash=OtpRequest.hash_otp(email, raw_otp),
            expires_at=now + ttl,
        )
    )
    await db.commit()

    await send_otp_email(email, raw_otp, settings.OTP_TTL_SECONDS // 60)

    response: dict[str, str] = {"message": "If that email can receive codes, a code is on its way."}
    if settings.ENVIRONMENT == "development" and settings.EXPOSE_DEV_OTP:
        response["_dev_otp"] = raw_otp
    return response


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(body: OtpVerifyRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Verify the emailed code and issue tokens.

      - wrong code ........ 400 INVALID_OTP (counts toward the attempt limit)
      - 5 wrong attempts .. 429 TOO_MANY_ATTEMPTS (request a new code)
      - expired ........... 400 OTP_EXPIRED
      - success ........... record marked used; user get-or-created; tokens issued
    """
    email = body.email.strip().lower()
    _throttle(request, "otp-verify", email)
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(OtpRequest)
        .where(OtpRequest.email == email, OtpRequest.used.is_(False))
        .order_by(OtpRequest.created_at.desc())
    )
    otp_record = result.scalars().first()

    if otp_record is None:
        raise _api_error(status.HTTP_400_BAD_REQUEST, "OTP_NOT_FOUND", "No pending code for this email. Request a new one.")

    if now > otp_record.expires_at:
        raise _api_error(status.HTTP_400_BAD_REQUEST, "OTP_EXPIRED", "This code has expired. Request a new one.")

    if otp_record.attempt_count >= settings.OTP_MAX_ATTEMPTS:
        raise _api_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "TOO_MANY_ATTEMPTS",
            "Too many incorrect attempts. Request a new code.",
        )

    submitted = OtpRequest.hash_otp(email, body.otp)
    if not hmac.compare_digest(submitted, otp_record.otp_hash):
        otp_record.attempt_count += 1
        await db.commit()
        remaining = settings.OTP_MAX_ATTEMPTS - otp_record.attempt_count
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_OTP",
            f"Incorrect code. {remaining} attempt(s) remaining.",
        )

    otp_record.used = True
    await db.flush()

    user_result = await db.execute(select(User).where(func.lower(User.email) == email))
    user = user_result.scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
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
