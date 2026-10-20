import asyncio
import uuid

from sqlalchemy import func, select

from app.models import PaymentEvent, Purchase
from tests.factories import make_tour
from tests.helpers import auth, signup
from tests.payments_helpers import (
    KEY_SECRET,
    checkout_signature,
    send_webhook,
    webhook_body,
)


async def _buy(client, token, tour_id):
    return await client.post("/purchases", json={"tour_id": str(tour_id)}, headers=auth(token))


async def _purchase(client, purchase_id) -> Purchase:
    async with client.session_factory() as db:
        return await db.get(Purchase, uuid.UUID(str(purchase_id)))


async def _count(client, model) -> int:
    async with client.session_factory() as db:
        return (await db.execute(select(func.count()).select_from(model))).scalar_one()


async def _start(client, razorpay):
    user = await signup(client)
    tour = await make_tour(client, price_paise=19900)
    resp = await _buy(client, user["access_token"], tour["id"])
    assert resp.status_code == 201, resp.text
    return user, tour, resp.json()


# ------------------------------------------------------------------ mock mode (dev)

async def test_mock_mode_completes_instantly_and_blocks_duplicates(client):
    user = await signup(client)
    tour = await make_tour(client)
    first = await _buy(client, user["access_token"], tour["id"])
    assert first.status_code == 201 and first.json()["status"] == "completed"
    again = await _buy(client, user["access_token"], tour["id"])
    assert again.status_code == 409 and again.json()["error"]["code"] == "TOUR_ALREADY_OWNED"


async def test_unpublished_tours_cannot_be_purchased(client):
    user = await signup(client)
    hidden = await make_tour(client, published=False)
    assert (await _buy(client, user["access_token"], hidden["id"])).status_code == 404


# ------------------------------------------------------------------ real mode: order creation

async def test_real_mode_creates_a_pending_order_with_checkout_config(client, razorpay):
    _, _, body = await _start(client, razorpay)
    assert body["status"] == "pending" and body["gateway_order_id"].startswith("order_")
    cfg = body["gateway_config"]
    assert cfg["provider"] == "razorpay" and cfg["order_id"] == body["gateway_order_id"]
    assert cfg["amount"] == 19900 and cfg["currency"] == "INR"
    assert KEY_SECRET not in str(body)  # the secret never leaves the server
    assert razorpay.orders_created[0]["amount"] == 19900


async def test_tapping_pay_twice_reuses_the_same_order(client, razorpay):
    user, tour, first = await _start(client, razorpay)
    second = await _buy(client, user["access_token"], tour["id"])
    assert second.status_code == 201
    assert second.json()["purchase_id"] == first["purchase_id"]
    assert second.json()["gateway_order_id"] == first["gateway_order_id"]
    assert len(razorpay.orders_created) == 1


async def test_concurrent_purchase_requests_create_one_purchase_and_one_order(client, razorpay):
    user = await signup(client)
    tour = await make_tour(client)
    results = await asyncio.gather(*[_buy(client, user["access_token"], tour["id"]) for _ in range(4)])
    assert all(r.status_code == 201 for r in results), [r.text for r in results]
    assert len({r.json()["purchase_id"] for r in results}) == 1
    assert await _count(client, Purchase) == 1
    assert len(razorpay.orders_created) == 1


async def test_gateway_outage_returns_502_and_can_be_retried(client, razorpay):
    user = await signup(client)
    tour = await make_tour(client)
    razorpay.down = True
    down = await _buy(client, user["access_token"], tour["id"])
    assert down.status_code == 502 and down.json()["error"]["code"] == "GATEWAY_ERROR"
    razorpay.down = False
    ok = await _buy(client, user["access_token"], tour["id"])
    assert ok.status_code == 201 and ok.json()["gateway_order_id"]
    assert await _count(client, Purchase) == 1


# ------------------------------------------------------------------ checkout verification

async def test_verify_with_valid_signature_completes_the_purchase(client, razorpay):
    user, _, body = await _start(client, razorpay)
    sig = checkout_signature(body["gateway_order_id"], "pay_123")
    resp = await client.post(
        f"/purchases/{body['purchase_id']}/verify",
        json={"razorpay_order_id": body["gateway_order_id"], "razorpay_payment_id": "pay_123", "razorpay_signature": sig},
        headers=auth(user["access_token"]),
    )
    assert resp.status_code == 200 and resp.json()["status"] == "completed"
    assert (await _purchase(client, body["purchase_id"])).gateway_payment_id == "pay_123"


async def test_verify_rejects_bad_signature_wrong_order_and_other_users(client, razorpay):
    user, _, body = await _start(client, razorpay)
    url = f"/purchases/{body['purchase_id']}/verify"
    order = body["gateway_order_id"]

    bad_sig = await client.post(url, headers=auth(user["access_token"]), json={
        "razorpay_order_id": order, "razorpay_payment_id": "pay_1", "razorpay_signature": "0" * 64})
    assert bad_sig.status_code == 400 and bad_sig.json()["error"]["code"] == "INVALID_SIGNATURE"

    wrong_order = await client.post(url, headers=auth(user["access_token"]), json={
        "razorpay_order_id": "order_other", "razorpay_payment_id": "pay_1",
        "razorpay_signature": checkout_signature("order_other", "pay_1")})
    assert wrong_order.status_code == 400

    stranger = await signup(client)
    other = await client.post(url, headers=auth(stranger["access_token"]), json={
        "razorpay_order_id": order, "razorpay_payment_id": "pay_1",
        "razorpay_signature": checkout_signature(order, "pay_1")})
    assert other.status_code == 404
    assert (await _purchase(client, body["purchase_id"])).status == "pending"


# ------------------------------------------------------------------ webhook

async def test_webhook_rejects_missing_or_bad_signature(client, razorpay):
    _, _, body = await _start(client, razorpay)
    raw = webhook_body("payment.captured", body["gateway_order_id"], "pay_1", 19900)
    assert (await send_webhook(client, raw, signature="")).status_code == 401
    assert (await send_webhook(client, raw, signature="f" * 64)).status_code == 401
    assert (await send_webhook(client, raw, secret="some-other-secret")).status_code == 401
    assert (await _purchase(client, body["purchase_id"])).status == "pending"
    assert await _count(client, PaymentEvent) == 0  # nothing stored for unsigned requests


async def test_signed_webhook_completes_the_purchase(client, razorpay):
    _, _, body = await _start(client, razorpay)
    raw = webhook_body("payment.captured", body["gateway_order_id"], "pay_1", 19900)
    assert (await send_webhook(client, raw, event_id="evt_1")).status_code == 204
    purchase = await _purchase(client, body["purchase_id"])
    assert purchase.status == "completed" and purchase.gateway_payment_id == "pay_1"


async def test_replayed_webhook_is_a_noop(client, razorpay):
    _, _, body = await _start(client, razorpay)
    raw = webhook_body("payment.captured", body["gateway_order_id"], "pay_1", 19900)
    for _ in range(3):
        assert (await send_webhook(client, raw, event_id="evt_same")).status_code == 204
    assert await _count(client, PaymentEvent) == 1
    assert await _count(client, Purchase) == 1
    assert (await _purchase(client, body["purchase_id"])).status == "completed"


async def test_two_different_events_for_one_payment_do_not_double_credit(client, razorpay):
    _, _, body = await _start(client, razorpay)
    order = body["gateway_order_id"]
    await send_webhook(client, webhook_body("payment.captured", order, "pay_1", 19900), event_id="evt_a")
    await send_webhook(client, webhook_body("order.paid", order, "pay_1", 19900), event_id="evt_b")
    assert await _count(client, Purchase) == 1
    purchase = await _purchase(client, body["purchase_id"])
    assert purchase.status == "completed" and purchase.gateway_payment_id == "pay_1"


async def test_concurrent_duplicate_webhooks_are_safe(client, razorpay):
    _, _, body = await _start(client, razorpay)
    raw = webhook_body("payment.captured", body["gateway_order_id"], "pay_1", 19900)
    results = await asyncio.gather(*[send_webhook(client, raw, event_id="evt_race") for _ in range(5)])
    assert all(r.status_code == 204 for r in results)
    assert await _count(client, PaymentEvent) == 1
    assert (await _purchase(client, body["purchase_id"])).status == "completed"


async def test_amount_mismatch_does_not_complete(client, razorpay):
    _, _, body = await _start(client, razorpay)
    raw = webhook_body("payment.captured", body["gateway_order_id"], "pay_1", 100)  # paid ₹1, not ₹199
    assert (await send_webhook(client, raw, event_id="evt_cheap")).status_code == 204
    assert (await _purchase(client, body["purchase_id"])).status == "pending"


async def test_failed_payment_allows_a_fresh_attempt(client, razorpay):
    user, tour, first = await _start(client, razorpay)
    raw = webhook_body("payment.failed", first["gateway_order_id"], "pay_bad", 19900)
    await send_webhook(client, raw, event_id="evt_fail")
    assert (await _purchase(client, first["purchase_id"])).status == "failed"

    retry = await _buy(client, user["access_token"], tour["id"])
    assert retry.status_code == 201
    assert retry.json()["purchase_id"] != first["purchase_id"]  # a new row, a new order
    assert retry.json()["gateway_order_id"] != first["gateway_order_id"]


async def test_late_capture_for_a_failed_purchase_still_completes_it(client, razorpay):
    _, _, body = await _start(client, razorpay)
    order = body["gateway_order_id"]
    await send_webhook(client, webhook_body("payment.failed", order, "pay_bad", 19900), event_id="e1")
    await send_webhook(client, webhook_body("payment.captured", order, "pay_ok", 19900), event_id="e2")
    assert (await _purchase(client, body["purchase_id"])).status == "completed"


async def test_late_event_cannot_resurrect_a_refunded_purchase(client, razorpay):
    _, _, body = await _start(client, razorpay)
    async with client.session_factory() as db:
        purchase = await db.get(Purchase, uuid.UUID(body["purchase_id"]))
        purchase.status = "refunded"
        await db.commit()
    raw = webhook_body("payment.captured", body["gateway_order_id"], "pay_1", 19900)
    await send_webhook(client, raw, event_id="evt_late")
    assert (await _purchase(client, body["purchase_id"])).status == "refunded"


async def test_unknown_order_and_unrelated_events_are_acknowledged(client, razorpay):
    assert (await send_webhook(client, webhook_body("payment.captured", "order_nope", "pay_1", 1), event_id="x1")).status_code == 204
    assert (await send_webhook(client, webhook_body("refund.created", "order_nope", "pay_1", 1), event_id="x2")).status_code == 204


async def test_malformed_signed_payload_is_a_400(client, razorpay):
    assert (await send_webhook(client, b"not json")).status_code == 400


async def test_webhook_is_disabled_in_mock_mode(client):
    resp = await send_webhook(client, webhook_body("payment.captured", "o", "p", 1))
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "MOCK_MODE_ACTIVE"


# ------------------------------------------------------------------ "check status" fallback

async def test_status_poll_recovers_a_lost_webhook(client, razorpay):
    user, _, body = await _start(client, razorpay)
    razorpay.payments_by_order[body["gateway_order_id"]] = [{"id": "pay_9", "status": "captured", "amount": 19900}]
    resp = await client.get(f"/purchases/{body['purchase_id']}", headers=auth(user["access_token"]))
    assert resp.status_code == 200 and resp.json()["status"] == "completed"


async def test_status_poll_survives_a_gateway_outage(client, razorpay):
    user, _, body = await _start(client, razorpay)
    razorpay.down = True
    resp = await client.get(f"/purchases/{body['purchase_id']}", headers=auth(user["access_token"]))
    assert resp.status_code == 200 and resp.json()["status"] == "pending"
