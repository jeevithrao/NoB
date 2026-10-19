import jwt
import pytest

from app.config import settings
from tests.helpers import auth, login, new_device, new_email, signup


async def test_signup_returns_tokens_and_user(client):
    user = await signup(client)
    assert user["access_token"] and user["refresh_token"]
    assert user["user"]["role"] == "user"
    assert "password" not in user["user"] and "password_hash" not in user["user"]


async def test_duplicate_signup_is_conflict(client):
    user = await signup(client)
    resp = await client.post(
        "/auth/signup",
        json={"email": user["email"], "password": "another-pass-1", "device_identifier": "x"},
    )
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "EMAIL_TAKEN"


@pytest.mark.parametrize("password", ["short", ""])
async def test_weak_password_rejected(client, password):
    resp = await client.post(
        "/auth/signup", json={"email": new_email(), "password": password, "device_identifier": "x"}
    )
    assert resp.status_code == 422


async def test_login_wrong_password_and_unknown_user_look_identical(client):
    user = await signup(client)
    wrong = await login(client, user["email"], "not-the-password", new_device())
    unknown = await login(client, new_email("ghost"), "whatever-123", new_device())
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()  # no account enumeration


async def test_me_requires_a_valid_token(client):
    assert (await client.get("/auth/me")).status_code == 401
    assert (await client.get("/auth/me", headers=auth("garbage"))).status_code == 401
    user = await signup(client)
    ok = await client.get("/auth/me", headers=auth(user["access_token"]))
    assert ok.status_code == 200 and ok.json()["email"] == user["email"]


async def test_refresh_token_cannot_be_used_as_access_token(client):
    user = await signup(client)
    resp = await client.get("/auth/me", headers=auth(user["refresh_token"]))
    assert resp.status_code == 401


async def test_tampered_token_rejected(client):
    user = await signup(client)
    forged = jwt.encode(
        {"sub": user["user"]["id"], "sid": "00000000-0000-0000-0000-000000000000", "type": "access", "role": "admin"},
        "wrong-secret", algorithm="HS256",
    )
    assert (await client.get("/auth/me", headers=auth(forged))).status_code == 401


async def test_refresh_issues_a_working_access_token(client):
    user = await signup(client)
    resp = await client.post(
        "/auth/refresh", json={"refresh_token": user["refresh_token"], "device_identifier": user["device"]}
    )
    assert resp.status_code == 200, resp.text
    me = await client.get("/auth/me", headers=auth(resp.json()["access_token"]))
    assert me.status_code == 200


async def test_logout_kills_the_session(client):
    user = await signup(client)
    assert (await client.post("/auth/logout", headers=auth(user["access_token"]))).status_code == 204
    assert (await client.get("/auth/me", headers=auth(user["access_token"]))).status_code == 401
    refresh = await client.post(
        "/auth/refresh", json={"refresh_token": user["refresh_token"], "device_identifier": user["device"]}
    )
    assert refresh.status_code == 401


# ----- single active session (Business Rules §3b) ---------------------------

async def test_login_on_device_b_kicks_out_device_a(client):
    a = await signup(client)  # device A
    b = await login(client, a["email"], a["password"], new_device())  # device B
    assert b.status_code == 200
    b_token = b.json()["access_token"]

    kicked = await client.get("/auth/me", headers=auth(a["access_token"]))
    assert kicked.status_code == 401
    assert kicked.json()["error"]["code"] == "SESSION_INVALIDATED"
    assert (await client.get("/auth/me", headers=auth(b_token))).status_code == 200


async def test_kicked_out_device_cannot_refresh(client):
    a = await signup(client)
    await login(client, a["email"], a["password"], new_device())
    resp = await client.post(
        "/auth/refresh", json={"refresh_token": a["refresh_token"], "device_identifier": a["device"]}
    )
    assert resp.status_code == 401 and resp.json()["error"]["code"] == "SESSION_INVALIDATED"


async def test_otp_login_also_kicks_out_other_device(client, outbox):
    a = await signup(client)
    await client.post("/auth/request-otp", json={"email": a["email"]})
    import re

    code = re.search(r"\b(\d{6})\b", outbox[-1].body).group(1)
    resp = await client.post(
        "/auth/verify-otp", json={"email": a["email"], "otp": code, "device_identifier": new_device()}
    )
    assert resp.status_code == 200
    assert (await client.get("/auth/me", headers=auth(a["access_token"]))).status_code == 401


async def test_only_one_active_login_session_per_user(client):
    a = await signup(client)
    for _ in range(3):
        await login(client, a["email"], a["password"], new_device())
    async with client.session_factory() as db:
        from sqlalchemy import func, select
        from app.models import UserLoginSession

        active = await db.execute(
            select(func.count()).select_from(UserLoginSession).where(UserLoginSession.is_active.is_(True))
        )
        assert active.scalar_one() == 1


async def test_expired_access_token_is_reported_as_expired(client, monkeypatch):
    monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", -1)
    user = await signup(client)
    resp = await client.get("/auth/me", headers=auth(user["access_token"]))
    assert resp.status_code == 401 and resp.json()["error"]["code"] == "TOKEN_EXPIRED"
