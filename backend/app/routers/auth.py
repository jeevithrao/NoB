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
from app.models import User, UserLoginSession
from app.schemas.auth import LoginRequest, RefreshRequest, SignupRequest, TokenResponse
from app.schemas.user import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


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

    # Note: the docs describe an OTP verification step here (email/SMS TBD by
    # provider choice). Skipped for this first build so the flow is testable
    # end-to-end without a messaging provider wired up — add /auth/verify-otp
    # later without changing this endpoint's shape.
    return await _issue_tokens(db, user, body.device_identifier)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise _api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS", "Incorrect email or password.")

    return await _issue_tokens(db, user, body.device_identifier)


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
