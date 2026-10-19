import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.config import settings
from app.models import Purchase
from tests.factories import make_neighbourhood, make_tour
from tests.helpers import arrive, auth, buy, complete_walk, signup, start_walk
from tests.payments_helpers import checkout_signature


async def _bookings(client, token, tab="all"):
    resp = await client.get("/purchases", params={"tab": tab}, headers=auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _refund(client, token, purchase_id):
    return await client.post(f"/purchases/{purchase_id}/refund", headers=auth(token))


async def _age_purchase(client, purchase_id, days):
    async with client.session_factory() as db:
        await db.execute(
            update(Purchase)
            .where(Purchase.id == uuid.UUID(str(purchase_id)))
            .values(created_at=datetime.now(timezone.utc) - timedelta(days=days))
        )
        await db.commit()


# ------------------------------------------------------------------ bookings list

async def test_bookings_empty_for_new_user(client):
    user = await signup(client)
    assert await _bookings(client, user["access_token"]) == []


async def test_bookings_requires_login(client):
    assert (await client.get("/purchases")).status_code == 401


async def test_booking_row_has_everything_the_screen_needs(client):
    hood = await make_neighbourhood(client, "Malleshwaram")
    tour = await make_tour(client, neighbourhood_id=hood.id, price_paise=19900, stops=3)
    user = await signup(client)
    bought = await buy(client, user["access_token"], tour["id"])
    (row,) = await _bookings(client, user["access_token"])
    assert row["purchase_id"] == bought["purchase_id"] and row["status"] == "completed"
    assert row["amount_paise"] == 19900 and row["tour"]["name"] and row["tour"]["neighbourhood"]["slug"] == hood.slug
    assert row["walk_status"] == "not_started" and row["stops_visited"] == 0 and row["stop_count"] == 3
    assert row["session_id"] is None and row["device_bound"] is False
    assert row["can_refund"] is True and row["refund_deadline"]


async def test_upcoming_and_past_tabs_follow_the_walk(client):
    t1, t2 = await make_tour(client), await make_tour(client)
    user = await signup(client)
    tok = user["access_token"]
    await buy(client, tok, t1["id"])
    await buy(client, tok, t2["id"])

    assert len(await _bookings(client, tok, "upcoming")) == 2 and await _bookings(client, tok, "past") == []

    session = await start_walk(client, tok, t1["id"])
    mid = {b["tour"]["id"]: b for b in await _bookings(client, tok)}
    assert mid[str(t1["id"])]["walk_status"] == "in_progress" and mid[str(t1["id"])]["session_id"] == session["id"]

    await arrive(client, tok, session["id"], t1["stop_ids"])
    await complete_walk(client, tok, session["id"])
    upcoming = await _bookings(client, tok, "upcoming")
    past = await _bookings(client, tok, "past")
    assert [b["tour"]["id"] for b in upcoming] == [str(t2["id"])]
    assert [b["tour"]["id"] for b in past] == [str(t1["id"])]
    assert past[0]["walk_status"] == "completed" and past[0]["can_refund"] is False and past[0]["session_id"] is None


async def test_bookings_are_private_and_hide_unfinished_payments(client, razorpay):
    tour = await make_tour(client)
    alice, bob = await signup(client), await signup(client)
    await client.post("/purchases", json={"tour_id": str(tour["id"])}, headers=auth(alice["access_token"]))  # pending
    assert await _bookings(client, alice["access_token"]) == []  # pending is not a booking
    assert await _bookings(client, bob["access_token"]) == []


async def test_bad_tab_is_rejected(client):
    user = await signup(client)
    assert (await client.get("/purchases", params={"tab": "soon"}, headers=auth(user["access_token"]))).status_code == 422


# ------------------------------------------------------------------ refunds

async def test_refund_before_starting_succeeds_and_frees_a_rebuy(client):
    tour = await make_tour(client)
    user = await signup(client)
    tok = user["access_token"]
    bought = await buy(client, tok, tour["id"])
    await client.post(f"/purchases/{bought['purchase_id']}/bind-device", json={"device_identifier": "dev-1"}, headers=auth(tok))

    resp = await _refund(client, tok, bought["purchase_id"])
    assert resp.status_code == 200 and resp.json()["status"] == "refunded"

    (row,) = await _bookings(client, tok, "past")
    assert row["status"] == "refunded" and row["device_bound"] is False and row["can_refund"] is False
    # The tour is locked again, and the user may buy it afresh.
    assert (await client.get(f"/tours/{tour['id']}", headers=auth(tok))).json()["status"] == "not_purchased"
    assert (await client.post("/sessions", json={"tour_id": str(tour["id"])}, headers=auth(tok))).status_code == 403
    again = await client.post("/purchases", json={"tour_id": str(tour["id"])}, headers=auth(tok))
    assert again.status_code == 201


async def test_refund_refused_once_a_stop_was_visited(client):
    tour = await make_tour(client)
    user = await signup(client)
    tok = user["access_token"]
    bought = await buy(client, tok, tour["id"])
    session = await start_walk(client, tok, tour["id"])
    await arrive(client, tok, session["id"], tour["stop_ids"][:1])
    resp = await _refund(client, tok, bought["purchase_id"])
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "REFUND_NOT_ELIGIBLE"
    (row,) = await _bookings(client, tok)
    assert row["can_refund"] is False and row["status"] == "completed"


async def test_refund_checks_every_session_not_only_the_latest(client):
    """Old code looked at the latest session only. An older session with progress must still block."""
    tour = await make_tour(client)
    user = await signup(client)
    tok = user["access_token"]
    bought = await buy(client, tok, tour["id"])
    first = await start_walk(client, tok, tour["id"])
    await arrive(client, tok, first["id"], tour["stop_ids"][:1])
    # a newer, empty session row appears (e.g. support reset / data quirk)
    from app.models import TourSession

    async with client.session_factory() as db:
        db.add(TourSession(user_id=uuid.UUID(user["user"]["id"]), tour_id=tour["id"], purchase_id=uuid.UUID(bought["purchase_id"])))
        await db.commit()
    assert (await _refund(client, tok, bought["purchase_id"])).status_code == 409


async def test_refund_refused_after_completion(client):
    tour = await make_tour(client)
    user = await signup(client)
    tok = user["access_token"]
    bought = await buy(client, tok, tour["id"])
    session = await start_walk(client, tok, tour["id"])
    await arrive(client, tok, session["id"], tour["stop_ids"])
    await complete_walk(client, tok, session["id"])
    resp = await _refund(client, tok, bought["purchase_id"])
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "REFUND_NOT_ELIGIBLE"


async def test_refund_window_boundaries(client):
    tour = await make_tour(client)
    user = await signup(client)
    tok = user["access_token"]
    bought = await buy(client, tok, tour["id"])
    await _age_purchase(client, bought["purchase_id"], settings.REFUND_WINDOW_DAYS + 1)
    (row,) = await _bookings(client, tok)
    assert row["can_refund"] is False
    resp = await _refund(client, tok, bought["purchase_id"])
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "REFUND_WINDOW_EXPIRED"

    await _age_purchase(client, bought["purchase_id"], settings.REFUND_WINDOW_DAYS - 1)
    assert (await _refund(client, tok, bought["purchase_id"])).status_code == 200


async def test_refund_window_is_configurable(client, monkeypatch):
    monkeypatch.setattr(settings, "REFUND_WINDOW_DAYS", 3)
    tour = await make_tour(client)
    user = await signup(client)
    bought = await buy(client, user["access_token"], tour["id"])
    await _age_purchase(client, bought["purchase_id"], 4)
    assert (await _refund(client, user["access_token"], bought["purchase_id"])).status_code == 409


async def test_refund_twice_and_other_users_purchase(client):
    tour = await make_tour(client)
    owner, stranger = await signup(client), await signup(client)
    bought = await buy(client, owner["access_token"], tour["id"])
    assert (await _refund(client, stranger["access_token"], bought["purchase_id"])).status_code == 404
    assert (await _refund(client, owner["access_token"], bought["purchase_id"])).status_code == 200
    second = await _refund(client, owner["access_token"], bought["purchase_id"])
    assert second.status_code == 400 and second.json()["error"]["code"] == "PURCHASE_NOT_COMPLETED"


async def test_real_mode_refund_calls_the_gateway_with_the_payment(client, razorpay):
    tour = await make_tour(client, price_paise=19900)
    user = await signup(client)
    tok = user["access_token"]
    bought = (await client.post("/purchases", json={"tour_id": str(tour["id"])}, headers=auth(tok))).json()
    order = bought["gateway_order_id"]
    await client.post(
        f"/purchases/{bought['purchase_id']}/verify", headers=auth(tok),
        json={"razorpay_order_id": order, "razorpay_payment_id": "pay_77", "razorpay_signature": checkout_signature(order, "pay_77")},
    )
    resp = await _refund(client, tok, bought["purchase_id"])
    assert resp.status_code == 200 and resp.json()["status"] == "refunded"
    assert razorpay.refunds == [("pay_77", 19900)]


async def test_real_mode_gateway_failure_leaves_the_purchase_untouched(client, razorpay):
    tour = await make_tour(client)
    user = await signup(client)
    tok = user["access_token"]
    bought = (await client.post("/purchases", json={"tour_id": str(tour["id"])}, headers=auth(tok))).json()
    order = bought["gateway_order_id"]
    await client.post(
        f"/purchases/{bought['purchase_id']}/verify", headers=auth(tok),
        json={"razorpay_order_id": order, "razorpay_payment_id": "pay_78", "razorpay_signature": checkout_signature(order, "pay_78")},
    )
    razorpay.down = True
    failed = await _refund(client, tok, bought["purchase_id"])
    assert failed.status_code == 502 and failed.json()["error"]["code"] == "GATEWAY_ERROR"
    assert (await _bookings(client, tok))[0]["status"] == "completed"  # still owned, can retry
    razorpay.down = False
    assert (await _refund(client, tok, bought["purchase_id"])).status_code == 200
