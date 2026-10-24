"""Rate limiting for the auth endpoints.

Two backends, chosen by `settings.rate_limit_backend`:
  * memory   - sliding window, per process (development, tests)
  * postgres - fixed window counters in the `rate_limit_hits` table, shared by every
               worker and container with no extra infrastructure. A fixed window can
               allow up to 2x the limit across a window boundary; that is fine here.
`await throttle(key, limit)` picks the backend.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status
from sqlalchemy import text

from app.config import settings


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str, limit: int, window_seconds: int = 60) -> None:
        now = time.monotonic()
        bucket = self._hits[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"error": {"code": "RATE_LIMITED", "message": "Too many requests. Please slow down and try again shortly."}},
                headers={"Retry-After": str(window_seconds)},
            )
        bucket.append(now)

    def reset(self) -> None:
        self._hits.clear()


limiter = SlidingWindowLimiter()


def _too_many(window_seconds: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={"error": {"code": "RATE_LIMITED", "message": "Too many requests. Please slow down and try again shortly."}},
        headers={"Retry-After": str(window_seconds)},
    )


_UPSERT = text(
    "INSERT INTO rate_limit_hits (key, window_start, hits) VALUES (:k, :w, 1) "
    "ON CONFLICT (key, window_start) DO UPDATE SET hits = rate_limit_hits.hits + 1 RETURNING hits"
)


async def postgres_hit(key: str, limit: int, window_seconds: int = 60, now: float | None = None) -> None:
    """Count one hit in a short transaction of its own, so a rolled-back request does not erase the count."""
    from app.database import engine  # late import: the engine is built from settings

    t = int(now if now is not None else time.time())
    window = t - (t % window_seconds)
    async with engine.begin() as conn:
        hits = (await conn.execute(_UPSERT, {"k": key[:300], "w": window})).scalar_one()
        if t % 97 == 0:  # opportunistic cleanup of old windows
            await conn.execute(text("DELETE FROM rate_limit_hits WHERE window_start < :old"), {"old": t - 3600})
    if hits > limit:
        raise _too_many(window_seconds)


async def throttle(key: str, limit: int, window_seconds: int = 60) -> None:
    if settings.rate_limit_backend == "postgres":
        await postgres_hit(key, limit, window_seconds)
    else:
        limiter.hit(key, limit, window_seconds)


def client_ip(request: Request) -> str:
    """Client IP. nginx appends the real peer address to X-Forwarded-For
    ($proxy_add_x_forwarded_for), so the LAST entry is the trustworthy one;
    earlier entries can be forged by the client."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"
