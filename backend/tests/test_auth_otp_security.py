"""Regression tests for the OTP account-takeover (the code used to be returned
in the API response, letting anyone sign in as any email, admin included)."""
import pytest
from sqlalchemy import update

from app.config import Settings, settings
from app.models import OtpRequest, User
from app.core.security import hash_password
from tests.helpers import auth, last_otp_code, login, new_device, new_email, signup


async def _request(client, email):
    return await client.post("/auth/request-otp", json={"email": email})


async def _verify(client, email, otp, device="dev-1"):
    return await client.post(
        "/auth/verify-otp", json={"email": email, "otp": otp, "device_identifier": device}
    )


async def test_otp_is_emailed_and_not_in_response(client, outbox):
    email = new_email()
    resp = await _request(client, email)
    assert resp.status_code == 200
    assert "_dev_otp" not in resp.json()
    assert len(outbox) == 1 and outbox[0].to == email
    assert len(last_otp_code()) == 6


async def test_attacker_cannot_take_over_existing_admin(client, db_engine):
    """The original exploit: request a code for admin@..., read it from the
    response, verify it. Now the attacker never sees the code."""
    async with client.session_factory() as db:
        db.add(User(email="admin@nob.app", password_hash=hash_password("x" * 12), role="admin"))
        await db.commit()

    resp = await _request(client, "admin@nob.app")
    assert resp.status_code == 200
    assert set(resp.json()) == {"message"}  # nothing but a generic message

    # Attacker's best remaining move is guessing; a wrong guess must fail.
    guess = await _verify(client, "admin@nob.app", "000000")
    assert guess.status_code in (400, 429)
    assert "access_token" not in guess.json()


async def test_verify_with_emailed_code_logs_in_and_creates_user(client):
    email = new_email()
    await _request(client, email)
    resp = await _verify(client, email, last_otp_code())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["email"] == email and body["user"]["role"] == "user"
    me = await client.get("/auth/me", headers=auth(body["access_token"]))
    assert me.status_code == 200


async def test_code_is_single_use(client):
    email = new_email()
    await _request(client, email)
    code = last_otp_code()
    assert (await _verify(client, email, code)).status_code == 200
    again = await _verify(client, email, code)
    assert again.status_code == 400 and again.json()["error"]["code"] == "OTP_NOT_FOUND"


async def test_five_wrong_attempts_lock_the_code(client):
    email = new_email()
    await _request(client, email)
    real = last_otp_code()
    wrong = "000000" if real != "000000" else "111111"
    for _ in range(settings.OTP_MAX_ATTEMPTS):
        r = await _verify(client, email, wrong)
        assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_OTP"
    locked = await _verify(client, email, wrong)
    assert locked.status_code == 429 and locked.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"
    # even the correct code is refused once locked
    assert (await _verify(client, email, real)).status_code == 429


async def test_expired_code_rejected(client):
    email = new_email()
    await _request(client, email)
    code = last_otp_code()
    async with client.session_factory() as db:
        await db.execute(
            update(OtpRequest).values(expires_at=OtpRequest.created_at)  # already in the past
        )
        await db.commit()
    resp = await _verify(client, email, code)
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "OTP_EXPIRED"


async def test_new_code_invalidates_old_one(client, outbox):
    email = new_email()
    await _request(client, email)
    first = last_otp_code()
    await _request(client, email)
    second = last_otp_code()
    if first != second:  # (1-in-a-million collision otherwise)
        assert (await _verify(client, email, first)).status_code == 400
    assert (await _verify(client, email, second)).status_code == 200


async def test_code_requests_are_capped_per_email(client):
    email = new_email()
    for _ in range(settings.OTP_MAX_REQUESTS_PER_WINDOW):
        assert (await _request(client, email)).status_code == 200
    blocked = await _request(client, email)
    assert blocked.status_code == 429 and blocked.json()["error"]["code"] == "OTP_REQUEST_LIMIT"


async def test_code_is_bound_to_email(client):
    a, b = new_email("a"), new_email("b")
    await _request(client, a)
    code_a = last_otp_code()
    await _request(client, b)
    code_b = last_otp_code()
    resp = await _verify(client, b, code_a)
    if code_a != code_b:  # (1-in-a-million collision otherwise)
        assert resp.status_code == 400


def test_hash_depends_on_email_and_is_not_plain_sha256():
    import hashlib

    h1 = OtpRequest.hash_otp("a@x.com", "123456")
    assert h1 != OtpRequest.hash_otp("b@x.com", "123456")
    assert h1 != hashlib.sha256(b"123456").hexdigest()
    assert h1 == OtpRequest.hash_otp(" A@X.com ", "123456")  # normalised


async def test_dev_echo_only_in_development_with_flag(client, monkeypatch):
    monkeypatch.setattr(settings, "EXPOSE_DEV_OTP", True)
    resp = await _request(client, new_email())
    assert "_dev_otp" in resp.json()

    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
    resp = await _request(client, new_email())
    assert "_dev_otp" not in resp.json()


@pytest.mark.parametrize(
    "overrides, fragment",
    [
        ({"SECRET_KEY": "change-this-please-0123456789012345678901"}, "SECRET_KEY"),
        ({"SECRET_KEY": "short"}, "SECRET_KEY"),
        ({"EXPOSE_DEV_OTP": True}, "EXPOSE_DEV_OTP"),
        ({"EMAIL_BACKEND": "console"}, "EMAIL_BACKEND"),
        ({"MOCK_PAYMENTS": True}, "MOCK_PAYMENTS"),
        ({"DEBUG": True}, "DEBUG"),
    ],
)
def test_production_refuses_unsafe_config(overrides, fragment):
    safe = dict(
        ENVIRONMENT="production",
        DATABASE_URL="postgresql+asyncpg://u:p@h/db",
        DATABASE_URL_SYNC="postgresql://u:p@h/db",
        SECRET_KEY="x" * 48,
        EMAIL_BACKEND="smtp",
        MOCK_PAYMENTS=False,
        EXPOSE_DEV_OTP=False,
        DEBUG=False,
    )
    Settings(_env_file=None, **safe)  # the safe baseline must load
    with pytest.raises(ValueError, match=fragment):
        Settings(_env_file=None, **{**safe, **overrides})


async def test_login_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_PER_MINUTE", 3)
    email = new_email()
    codes = []
    for _ in range(5):
        r = await login(client, email, "wrong-password", new_device())
        codes.append(r.status_code)
    assert codes[:3] == [401, 401, 401]
    assert codes[3] == 429


async def test_email_matching_is_case_insensitive(client):
    user = await signup(client, email="MixedCase@Nobtests.com")
    resp = await login(client, "mixedcase@nobtests.com", user["password"], new_device())
    assert resp.status_code == 200
    dup = await client.post(
        "/auth/signup",
        json={"email": "MIXEDCASE@nobtests.com", "password": "correct-horse-1", "device_identifier": "d"},
    )
    assert dup.status_code == 409
