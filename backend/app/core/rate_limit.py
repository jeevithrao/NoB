"""Tiny in-memory sliding-window rate limiter.

Counts are per-process, which is fine for a single API container. If the API
is scaled to several workers/containers, swap `SlidingWindowLimiter` for a
Redis-backed implementation with the same `hit()` signature.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


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


def client_ip(request: Request) -> str:
    """Client IP. Behind nginx the proxy must set X-Forwarded-For (it does in
    nginx.conf); only the first hop is trusted."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
