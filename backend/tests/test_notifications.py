"""The bell: creation at the right moments, idempotency, reading and dismissing."""
import uuid

from sqlalchemy import func, select

from app.models import Notification
from tests.factories import make_admin, make_neighbourhood, make_tour
from tests.helpers import auth, buy, complete_walk, signup, start_walk
from tests.payments_helpers import checkout_signature


async def _list(client, token, **params):
    resp = await client.get("/me/notifications", params=params, headers=auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _count_all(client) -> int:
    async with client.session_factory() as db:
        return (await db.execute(select(func.count()).select_from(Notification))).scalar_one()


async def _publish_new_tour(client, admin_token, **fields):
    created = await client.post("/admin/tours", json={"name": f"Fresh {uuid.uuid4().hex[:5]}", "price_paise": 19900, "distance_km": 2.0, **fields}, headers=auth(admin_token))
    assert created.status_code == 201, created.text
    tour_id = created.json()["id"]
    await client.post(
        f"/admin/tours/{tour_id}/stops",
        json={"order_index": 1, "name": "S1", "lat": 12.97, "lng": 77.59, "audio_filename": "x.mp3"},
        headers=auth(admin_token),
    )
    return created.json(), (await client.post(f"/admin/tours/{tour_id}/publish", headers=auth(admin_token)))


# ---------------------------------------------------------------- basics

async def test_empty_bell_and_login_required(client):
    assert (await client.get("/me/notifications")).status_code == 401
    user = await signup(client)
    assert await _list(client, user["access_token"]) == {"unread_count": 0, "items": []}


# ---------------------------------------------------------------- purchase confirmed

async def test_buying_creates_one_confirmation(client):
    tour = await make_tour(client, name="Silk Walk")
    user = await signup(client)
    tok = user["access_token"]
    await buy(client, tok, tour["id"])
    body = await _list(client, tok)
    assert body["unread_count"] == 1
    (item,) = body["items"]
    assert item["type"] == "confirmed" and item["title"] == "You're in!" and "Silk Walk" in item["subtitle"]
    assert item["tour_id"] == str(tour["id"]) and item["is_read"] is False


async def test_free_claim_also_confirms(client):
    tour = await make_tour(client, is_free=True)
    user = await signup(client)
    await client.post("/purchases", json={"tour_id": str(tour["id"])}, headers=auth(user["access_token"]))
    assert [n["type"] for n in (await _list(client, user["access_token"]))["items"]] == ["confirmed"]


async def test_real_payment_confirms_once_even_if_verified_twice(client, razorpay):
    user = await signup(client)
    tour = await make_tour(client, price_paise=19900)
    tok = user["access_token"]
    body = (await client.post("/purchases", json={"tour_id": str(tour["id"])}, headers=auth(tok))).json()
    assert (await _list(client, tok))["items"] == []  # still pending: no "You're in!" yet
    payload = {
        "razorpay_order_id": body["gateway_order_id"],
        "razorpay_payment_id": "pay_1",
        "razorpay_signature": checkout_signature(body["gateway_order_id"], "pay_1"),
    }
    for _ in range(2):
        assert (await client.post(f"/purchases/{body['purchase_id']}/verify", json=payload, headers=auth(tok))).status_code == 200
    assert len((await _list(client, tok))["items"]) == 1


# ---------------------------------------------------------------- walk completed

async def test_completing_a_walk_asks_for_a_review_once(client):
    tour = await make_tour(client, name="Book Lanes")
    user = await signup(client)
    tok = user["access_token"]
    await buy(client, tok, tour["id"])
    session = await start_walk(client, tok, tour["id"])
    await complete_walk(client, tok, session["id"])
    await complete_walk(client, tok, session["id"])  # idempotent
    reviews = [n for n in (await _list(client, tok))["items"] if n["type"] == "review"]
    assert len(reviews) == 1 and "Book Lanes" in reviews[0]["subtitle"] and reviews[0]["title"] == "How was your walk?"


# ---------------------------------------------------------------- new walk published

async def test_publishing_announces_the_walk_to_users_with_notifications_on(client):
    hood = await make_neighbourhood(client, "Yelahanka")
    admin = await make_admin(client)
    on, off, other = await signup(client), await signup(client), await signup(client)
    await client.patch("/me/preferences", json={"notifications_enabled": False}, headers=auth(off["access_token"]))

    tour, resp = await _publish_new_tour(client, admin["access_token"], neighbourhood_id=str(hood.id))
    assert resp.status_code == 200
    for user in (on, other):
        (item,) = [n for n in (await _list(client, user["access_token"]))["items"] if n["type"] == "new"]
        assert item["title"] == f"New walk: {tour['name']}" and item["subtitle"] == "Yelahanka · 2km · ₹199"
        assert item["tour_id"] == tour["id"]
    assert (await _list(client, off["access_token"]))["items"] == []
    assert (await _list(client, admin["access_token"]))["items"] == []  # staff are not "walkers"


async def test_republishing_does_not_notify_again(client):
    admin = await make_admin(client)
    user = await signup(client)
    tour, _ = await _publish_new_tour(client, admin["access_token"])
    await client.post(f"/admin/tours/{tour['id']}/publish", headers=auth(admin["access_token"]))
    assert len((await _list(client, user["access_token"]))["items"]) == 1


async def test_free_walk_announcement_says_free(client):
    admin = await make_admin(client)
    user = await signup(client)
    tour, _ = await _publish_new_tour(client, admin["access_token"], price_paise=0, is_free=True)
    (item,) = (await _list(client, user["access_token"]))["items"]
    assert item["subtitle"].endswith("Free")


async def test_notifications_off_means_no_confirmation(client):
    tour = await make_tour(client)
    user = await signup(client)
    tok = user["access_token"]
    await client.patch("/me/preferences", json={"notifications_enabled": False}, headers=auth(tok))
    await buy(client, tok, tour["id"])
    assert (await _list(client, tok))["items"] == []


# ---------------------------------------------------------------- reading and dismissing

async def _three(client):
    user = await signup(client)
    tok = user["access_token"]
    for _ in range(3):
        tour = await make_tour(client)
        await buy(client, tok, tour["id"])
    return user, tok


async def test_newest_first_limit_and_unread_count_covers_everything(client):
    user, tok = await _three(client)
    full = await _list(client, tok)
    stamps = [n["created_at"] for n in full["items"]]
    assert stamps == sorted(stamps, reverse=True) and full["unread_count"] == 3
    page = await _list(client, tok, limit=1)
    assert len(page["items"]) == 1 and page["unread_count"] == 3


async def test_mark_one_read_then_all_read_and_unread_filter(client):
    user, tok = await _three(client)
    first = (await _list(client, tok))["items"][0]
    done = await client.post(f"/me/notifications/{first['id']}/read", headers=auth(tok))
    assert done.status_code == 200 and done.json()["is_read"] is True
    body = await _list(client, tok)
    assert body["unread_count"] == 2 and len((await _list(client, tok, unread_only=True))["items"]) == 2

    assert (await client.post("/me/notifications/read-all", headers=auth(tok))).status_code == 204
    after = await _list(client, tok)
    assert after["unread_count"] == 0 and len(after["items"]) == 3  # read, not removed


async def test_dismiss_removes_it(client):
    user, tok = await _three(client)
    target = (await _list(client, tok))["items"][0]["id"]
    assert (await client.delete(f"/me/notifications/{target}", headers=auth(tok))).status_code == 204
    body = await _list(client, tok)
    assert target not in {n["id"] for n in body["items"]} and body["unread_count"] == 2
    again = await client.delete(f"/me/notifications/{target}", headers=auth(tok))
    assert again.status_code == 404 and again.json()["error"]["code"] == "NOTIFICATION_NOT_FOUND"


async def test_cannot_touch_someone_elses_notifications(client):
    user, tok = await _three(client)
    stranger = await signup(client)
    target = (await _list(client, tok))["items"][0]["id"]
    assert (await client.post(f"/me/notifications/{target}/read", headers=auth(stranger["access_token"]))).status_code == 404
    assert (await client.delete(f"/me/notifications/{target}", headers=auth(stranger["access_token"]))).status_code == 404
    assert (await client.post("/me/notifications/read-all", headers=auth(stranger["access_token"]))).status_code == 204
    assert (await _list(client, tok))["unread_count"] == 3  # untouched
    assert (await client.delete(f"/me/notifications/{target}")).status_code == 401


async def test_deleting_the_account_erases_notifications(client):
    user, tok = await _three(client)
    assert await _count_all(client) >= 3
    await client.request("DELETE", "/me", json={"confirm": "DELETE"}, headers=auth(tok))
    async with client.session_factory() as db:
        left = (
            await db.execute(select(func.count()).select_from(Notification).where(Notification.user_id == uuid.UUID(user["user"]["id"])))
        ).scalar_one()
    assert left == 0
