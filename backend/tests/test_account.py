"""Profile, preferences, data export, account deletion and password reset."""
import uuid

from sqlalchemy import select

from app.models import OtpRequest, Purchase, TourComment, TourRating, User
from tests.factories import make_admin, make_tour
from tests.helpers import auth, buy, complete_walk, last_otp_code, login, new_device, new_email, signup, start_walk


# ---------------------------------------------------------------- profile

async def test_profile_requires_login_and_shows_defaults(client):
    assert (await client.get("/me")).status_code == 401
    user = await signup(client)
    body = (await client.get("/me", headers=auth(user["access_token"]))).json()
    assert body["email"] == user["email"] and body["username"] is None
    assert body["notifications_enabled"] is True and body["analytics_opt_in"] is False and body["marketing_opt_in"] is False


async def test_update_name_and_username_normalises(client):
    user = await signup(client)
    tok = user["access_token"]
    resp = await client.patch("/me", json={"full_name": "  Priya   Sharma ", "username": "@Priya_Walks"}, headers=auth(tok))
    assert resp.status_code == 200, resp.text
    assert resp.json()["full_name"] == "Priya Sharma" and resp.json()["username"] == "priya_walks"
    assert (await client.get("/auth/me", headers=auth(tok))).json()["username"] == "priya_walks"


async def test_partial_update_leaves_other_fields_alone(client):
    user = await signup(client)
    tok = user["access_token"]
    await client.patch("/me", json={"username": "walker_one"}, headers=auth(tok))
    resp = await client.patch("/me", json={"full_name": "New Name"}, headers=auth(tok))
    assert resp.json()["username"] == "walker_one" and resp.json()["full_name"] == "New Name"
    cleared = await client.patch("/me", json={"username": None}, headers=auth(tok))
    assert cleared.json()["username"] is None and cleared.json()["full_name"] == "New Name"


async def test_username_rules(client):
    a, b = await signup(client), await signup(client)
    assert (await client.patch("/me", json={"username": "taken_name"}, headers=auth(a["access_token"]))).status_code == 200
    dup = await client.patch("/me", json={"username": "Taken_Name"}, headers=auth(b["access_token"]))
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "USERNAME_TAKEN"
    own = await client.patch("/me", json={"username": "taken_name"}, headers=auth(a["access_token"]))
    assert own.status_code == 200  # keeping your own is fine
    for bad in ("ab", "has space", "a" * 31, "emoji😀name"):
        resp = await client.patch("/me", json={"username": bad}, headers=auth(b["access_token"]))
        assert resp.status_code == 422 and resp.json()["error"]["code"] == "VALIDATION_ERROR", bad


async def test_blank_name_rejected_and_email_cannot_be_changed(client):
    user = await signup(client)
    tok = user["access_token"]
    assert (await client.patch("/me", json={"full_name": "   "}, headers=auth(tok))).status_code == 422
    resp = await client.patch("/me", json={"email": "hacker@nobtests.com", "full_name": "Ok"}, headers=auth(tok))
    assert resp.status_code == 200 and resp.json()["email"] == user["email"]


# ---------------------------------------------------------------- preferences

async def test_preferences_are_partial_and_persist(client):
    user = await signup(client)
    tok = user["access_token"]
    one = await client.patch("/me/preferences", json={"analytics_opt_in": True}, headers=auth(tok))
    assert one.json()["analytics_opt_in"] is True and one.json()["notifications_enabled"] is True
    two = await client.patch("/me/preferences", json={"notifications_enabled": False, "marketing_opt_in": True}, headers=auth(tok))
    body = two.json()
    assert (body["analytics_opt_in"], body["notifications_enabled"], body["marketing_opt_in"]) == (True, False, True)
    assert (await client.get("/me", headers=auth(tok))).json()["notifications_enabled"] is False
    assert (await client.patch("/me/preferences", json={"analytics_opt_in": True})).status_code == 401


# ---------------------------------------------------------------- export

async def test_export_contains_my_data_and_no_secrets(client):
    tour = await make_tour(client, name="Exported walk")
    user = await signup(client)
    tok = user["access_token"]
    await buy(client, tok, tour["id"])
    session = await start_walk(client, tok, tour["id"])
    await complete_walk(client, tok, session["id"])
    await client.put(f"/tours/{tour['id']}/rating", json={"rating": 5}, headers=auth(tok))
    await client.post(f"/tours/{tour['id']}/comments", json={"comment_text": "Loved it"}, headers=auth(tok))

    resp = await client.get("/me/export", headers=auth(tok))
    assert resp.status_code == 200 and "attachment" in resp.headers["content-disposition"]
    data = resp.json()
    assert data["profile"]["email"] == user["email"]
    assert data["consent"]["terms_version"] and data["consent"]["terms_accepted_at"]
    assert data["purchases"][0]["tour"] == "Exported walk" and data["purchases"][0]["booking_ref"].startswith("NOB-")
    assert data["walks"][0]["completed"] is True
    assert data["ratings"] == [{"tour": "Exported walk", "rating": 5}]
    assert data["comments"][0]["text"] == "Loved it"
    for secret in ("password", "refresh_token", "otp"):
        assert secret not in resp.text.lower()


async def test_export_never_includes_other_peoples_data(client):
    tour = await make_tour(client)
    a, b = await signup(client), await signup(client)
    await buy(client, a["access_token"], tour["id"])
    data = (await client.get("/me/export", headers=auth(b["access_token"]))).json()
    assert data["purchases"] == [] and a["email"] not in str(data)
    assert (await client.get("/me/export")).status_code == 401


# ---------------------------------------------------------------- delete account

async def test_delete_needs_explicit_confirmation(client):
    user = await signup(client)
    tok = user["access_token"]
    for body in ({}, {"confirm": "yes"}, {"confirm": "delete"}):
        resp = await client.request("DELETE", "/me", json=body, headers=auth(tok))
        assert resp.status_code == 422, body
    assert (await client.get("/me", headers=auth(tok))).status_code == 200


async def test_admin_cannot_delete_themselves_here(client):
    admin = await make_admin(client)
    resp = await client.request("DELETE", "/me", json={"confirm": "DELETE"}, headers=auth(admin["access_token"]))
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "ADMIN_CANNOT_BE_DELETED"


async def test_delete_erases_personal_data_signs_out_and_keeps_financial_records(client):
    tour = await make_tour(client)
    user = await signup(client)
    tok = user["access_token"]
    bought = await buy(client, tok, tour["id"])
    session = await start_walk(client, tok, tour["id"])
    await complete_walk(client, tok, session["id"])
    await client.put(f"/tours/{tour['id']}/rating", json={"rating": 4}, headers=auth(tok))
    await client.post(f"/tours/{tour['id']}/comments", json={"comment_text": "private words"}, headers=auth(tok))
    await client.post("/auth/request-otp", json={"email": user["email"]})

    resp = await client.request("DELETE", "/me", json={"confirm": "DELETE"}, headers=auth(tok))
    assert resp.status_code == 204

    # signed out everywhere, credentials dead
    assert (await client.get("/me", headers=auth(tok))).status_code == 401
    assert (await login(client, user["email"], user["password"], new_device())).status_code == 401
    refresh = await client.post("/auth/refresh", json={"refresh_token": user["refresh_token"], "device_identifier": user["device"]})
    assert refresh.status_code == 401

    async with client.session_factory() as db:
        row = (await db.execute(select(User).where(User.id == uuid.UUID(user["user"]["id"])))).scalar_one()
        assert row.email.endswith("@deleted.invalid") and user["email"] not in row.email
        assert row.full_name is None and row.username is None and row.deleted_at is not None
        assert (await db.execute(select(TourComment).where(TourComment.user_id == row.id))).first() is None
        assert (await db.execute(select(TourRating).where(TourRating.user_id == row.id))).first() is None
        assert (await db.execute(select(OtpRequest).where(OtpRequest.email == user["email"]))).first() is None
        kept = (await db.execute(select(Purchase).where(Purchase.id == uuid.UUID(bought["purchase_id"])))).scalar_one()
        assert kept.amount_paise == tour["price_paise"]  # accounting record survives, now unlinked from a person
    assert "private words" not in (await client.get("/reviews")).text


async def test_email_can_be_reused_after_deletion(client):
    user = await signup(client)
    await client.request("DELETE", "/me", json={"confirm": "DELETE"}, headers=auth(user["access_token"]))
    again = await client.post(
        "/auth/signup",
        json={"email": user["email"], "password": "correct-horse-2", "device_identifier": new_device(), "accepted_terms": True},
    )
    assert again.status_code == 201 and again.json()["user"]["id"] != user["user"]["id"]


# ---------------------------------------------------------------- forgot / reset password

async def _forgot(client, email):
    return await client.post("/auth/forgot-password", json={"email": email})


async def test_reset_password_happy_path(client, outbox):
    user = await signup(client)
    outbox.clear()
    resp = await _forgot(client, user["email"])
    assert resp.status_code == 200 and "_dev_otp" not in resp.json()
    assert len(outbox) == 1 and outbox[0].to == user["email"] and "reset" in outbox[0].subject.lower()
    code = last_otp_code()

    done = await client.post("/auth/reset-password", json={"email": user["email"], "otp": code, "new_password": "brand-new-pass-1"})
    assert done.status_code == 204
    assert (await login(client, user["email"], user["password"], new_device())).status_code == 401
    assert (await login(client, user["email"], "brand-new-pass-1", new_device())).status_code == 200


async def test_reset_signs_out_existing_sessions(client, outbox):
    user = await signup(client)
    await _forgot(client, user["email"])
    await client.post("/auth/reset-password", json={"email": user["email"], "otp": last_otp_code(), "new_password": "brand-new-pass-1"})
    assert (await client.get("/me", headers=auth(user["access_token"]))).status_code == 401


async def test_reset_code_is_single_use(client, outbox):
    user = await signup(client)
    await _forgot(client, user["email"])
    code = last_otp_code()
    body = {"email": user["email"], "otp": code, "new_password": "brand-new-pass-1"}
    assert (await client.post("/auth/reset-password", json=body)).status_code == 204
    again = await client.post("/auth/reset-password", json={**body, "new_password": "another-new-pass-2"})
    assert again.status_code == 400
    assert (await login(client, user["email"], "brand-new-pass-1", new_device())).status_code == 200


async def test_wrong_code_is_rejected_and_attempts_are_limited(client, outbox):
    user = await signup(client)
    await _forgot(client, user["email"])
    real = last_otp_code()
    wrong = "000000" if real != "000000" else "111111"
    body = {"email": user["email"], "otp": wrong, "new_password": "brand-new-pass-1"}
    for _ in range(5):
        assert (await client.post("/auth/reset-password", json=body)).json()["error"]["code"] == "INVALID_OTP"
    locked = await client.post("/auth/reset-password", json={**body, "otp": real})
    assert locked.status_code == 429 and locked.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"
    assert (await login(client, user["email"], user["password"], new_device())).status_code == 200  # password unchanged


async def test_login_code_cannot_reset_a_password_and_vice_versa(client, outbox):
    user = await signup(client)
    await client.post("/auth/request-otp", json={"email": user["email"]})
    login_code = last_otp_code()
    resp = await client.post("/auth/reset-password", json={"email": user["email"], "otp": login_code, "new_password": "brand-new-pass-1"})
    assert resp.status_code == 400  # no reset code pending

    await _forgot(client, user["email"])
    reset_code = last_otp_code()
    cross = await client.post("/auth/verify-otp", json={"email": user["email"], "otp": reset_code, "device_identifier": new_device()})
    assert cross.status_code == 400 and cross.json()["error"]["code"] in ("INVALID_OTP", "OTP_NOT_FOUND")
    # and the login code is still valid for logging in (separate purposes don't cancel each other)
    ok = await client.post("/auth/verify-otp", json={"email": user["email"], "otp": login_code, "device_identifier": new_device()})
    assert ok.status_code == 200


async def test_unknown_email_looks_identical_and_sends_nothing(client, outbox):
    known = await signup(client)
    outbox.clear()
    a = await _forgot(client, known["email"])
    b = await _forgot(client, new_email("ghost"))
    assert a.status_code == b.status_code == 200 and a.json() == b.json()
    assert [m.to for m in outbox] == [known["email"]]  # nothing sent to the unknown address

    # the request limit hits both cases at the same point (no enumeration through 429s)
    fresh = await signup(client)
    ghost = new_email("ghost")
    real_codes = [(await _forgot(client, fresh["email"])).status_code for _ in range(5)]
    ghost_codes = [(await _forgot(client, ghost)).status_code for _ in range(5)]
    assert real_codes == ghost_codes and 429 in real_codes


async def test_reset_validates_password_and_code_shape(client):
    email = new_email()
    short = await client.post("/auth/reset-password", json={"email": email, "otp": "123456", "new_password": "short"})
    assert short.status_code == 422 and "new_password" in short.json()["error"]["fields"]
    bad_code = await client.post("/auth/reset-password", json={"email": email, "otp": "12ab56", "new_password": "long-enough-pass"})
    assert bad_code.status_code == 422 and "otp" in bad_code.json()["error"]["fields"]


async def test_deleted_account_cannot_be_reset(client, outbox):
    user = await signup(client)
    await client.request("DELETE", "/me", json={"confirm": "DELETE"}, headers=auth(user["access_token"]))
    outbox.clear()
    resp = await _forgot(client, user["email"])
    assert resp.status_code == 200 and outbox == []
