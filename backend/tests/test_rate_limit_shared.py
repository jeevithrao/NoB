"""The Postgres-backed limiter: counts survive across workers because they live in the database."""
import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.config import settings
from app.core.rate_limit import postgres_hit, throttle
from tests.helpers import new_device, new_email


@pytest.fixture(autouse=True)
async def _release_app_engine():
    """Each test runs on its own event loop; drop pooled connections bound to the previous one."""
    from app.database import engine
    await engine.dispose()
    yield
    await engine.dispose()


async def test_hits_over_the_limit_are_refused_and_a_new_window_starts_fresh():
    await postgres_hit("k:a", 2, 60, now=1_000_020)
    await postgres_hit("k:a", 2, 60, now=1_000_030)
    with pytest.raises(HTTPException) as e:
        await postgres_hit("k:a", 2, 60, now=1_000_020)
    assert e.value.status_code == 429 and e.value.detail["error"]["code"] == "RATE_LIMITED"
    await postgres_hit("k:a", 2, 60, now=1_000_090)  # next window


async def test_keys_are_independent():
    for _ in range(2):
        await postgres_hit("k:one", 2, 60, now=2_000_000)
    await postgres_hit("k:two", 2, 60, now=2_000_000)


async def test_counts_are_stored_in_the_database_not_in_the_process(sync_engine):
    await postgres_hit("k:shared", 5, 60, now=3_000_000)
    await postgres_hit("k:shared", 5, 60, now=3_000_001)
    with sync_engine.begin() as conn:
        hits = conn.execute(text("SELECT hits FROM rate_limit_hits WHERE key='k:shared'")).scalar_one()
    assert hits == 2


async def test_login_is_throttled_through_postgres(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "postgres")
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_PER_MINUTE", 3)
    email = new_email()
    codes = []
    for _ in range(10):  # more than two windows' worth, so a minute boundary cannot hide the 429
        r = await client.post("/auth/login", json={"email": email, "password": "wrong-password-1", "device_identifier": new_device()})
        codes.append(r.status_code)
    assert 429 in codes and codes[0] == 401


def test_backend_choice(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "auto")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    assert settings.rate_limit_backend == "memory"
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
    assert settings.rate_limit_backend == "postgres"
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "memory")
    assert settings.rate_limit_backend == "memory"


async def test_throttle_uses_memory_backend_in_development(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "memory")
    await throttle("m:key", 1)
    with pytest.raises(HTTPException):
        await throttle("m:key", 1)


async def test_event_batches_are_capped(client):
    from tests.helpers import signup, auth
    user = await signup(client)
    resp = await client.post(
        "/sessions/00000000-0000-0000-0000-000000000000/events/batch",
        json={"events": [{"client_event_id": "00000000-0000-0000-0000-%012d" % i, "stop_id": "00000000-0000-0000-0000-000000000001",
                          "event_type": "arrived", "occurred_at": "2026-01-01T00:00:00Z"} for i in range(201)]},
        headers=auth(user["access_token"]),
    )
    assert resp.status_code == 422
