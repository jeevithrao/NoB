import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.database import get_db
from app.models import User, UserLoginSession

bearer_scheme = HTTPBearer(auto_error=False)


def _auth_error(detail: str, code: str = "UNAUTHORIZED") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": code, "message": detail}},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _resolve_auth(
    credentials: HTTPAuthorizationCredentials | None, db: AsyncSession
) -> tuple[User, UserLoginSession]:
    if credentials is None:
        raise _auth_error("Missing bearer token.")

    try:
        payload = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise _auth_error("Access token expired.", "TOKEN_EXPIRED")
    except jwt.InvalidTokenError:
        raise _auth_error("Invalid access token.")

    if payload.get("type") != "access":
        raise _auth_error("Wrong token type.")

    try:
        user_id = uuid.UUID(payload["sub"])
        login_session_id = uuid.UUID(payload["sid"])
    except (KeyError, ValueError):
        raise _auth_error("Malformed token payload.")

    # Enforce single-active-session: the login session this token was minted
    # from must still be active. Logging in on a new device flips this to
    # False, which immediately invalidates every token issued for the old one.
    session_result = await db.execute(
        select(UserLoginSession).where(UserLoginSession.id == login_session_id)
    )
    login_session = session_result.scalar_one_or_none()
    if login_session is None or not login_session.is_active:
        raise _auth_error(
            "Session no longer active — you were logged out because this account "
            "signed in on another device.",
            "SESSION_INVALIDATED",
        )

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise _auth_error("User not found.")

    return user, login_session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    return (await _resolve_auth(credentials, db))[0]


async def get_login_device(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> str:
    """The device the caller signed in on (their one active login session)."""
    return (await _resolve_auth(credentials, db))[1].device_id


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Same as get_current_user but returns None instead of raising when no
    (or an invalid) token is present — used by endpoints like the tour catalog
    that are browsable while logged out but personalize status when logged in."""
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "ADMIN_REQUIRED", "message": "Admin role required."}},
        )
    return user
