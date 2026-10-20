"""Moving a purchase to a new device (cleared browser storage, new phone)."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.models import Purchase
from tests.factories import make_tour
from tests.helpers import auth, buy, complete_walk, login, new_device, signup, start_walk


async def _bound_owner(client, stops=2):
    """A user who bought a walk and bound it on their sign-up device."""
    tour = await make_tour(client, stops=stops)
    user = await signup(client)
    bought = await buy(client, user["access_token"], tour["id"])
    resp = await client.post(
        f"/purchases/{bought['purchase_id']}/bind-device",
        json={"device_identifier": user["device"]},
        headers=auth(user["access_token"]),
    )
    assert resp.status_code == 200
    return tour, user, bought["purchase_id"]


async def _sign_in_elsewhere(client, user):
    device = new_device()
    resp = await login(client, user["email"], user["password"], device)
    assert resp.status_code == 200
    return device, resp.json()["access_token"]


async def _row(client, token):
    (row,) = (await client.get("/purchases", headers=auth(token))).json()
    return row


def _rebind(client, token, purchase_id, device):
    return client.post(f"/purchases/{purchase_id}/rebind-device", json={"device_identifier": device}, headers=auth(token))


async def _age_rebind(client, purchase_id, days):
    async with client.session_factory() as db:
        await db.execute(
            update(Purchase)
            .where(Purchase.id == uuid.UUID(str(purchase_id)))
            .values(device_rebound_at=datetime.now(timezone.utc) - timedelta(days=days))
        )
        await db.commit()


async def test_device_status_follows_binding(client):
    tour = await make_tour(client)
    user = await signup(client)
    tok = user["access_token"]
    bought = await buy(client, tok, tour["id"])
    assert (await _row(client, tok))["device_status"] == "unbound"
    await client.post(f"/purchases/{bought['purchase_id']}/bind-device", json={"device_identifier": user["device"]}, headers=auth(tok))
    row = await _row(client, tok)
    assert row["device_status"] == "this_device" and row["device_bound"] is True


async def test_new_device_is_locked_out_until_it_moves_the_walk(client):
    tour, user, pid = await _bound_owner(client)
    device_b, token_b = await _sign_in_elsewhere(client, user)

    row = await _row(client, token_b)
    assert row["device_status"] == "other_device" and row["rebind_available_at"] is None  # allowed right now
    blocked_walk = await client.post("/sessions", json={"tour_id": str(tour["id"])}, headers=auth(token_b))
    assert blocked_walk.status_code == 409 and blocked_walk.json()["error"]["code"] == "BOUND_TO_OTHER_DEVICE"
    blocked_pkg = await client.get(f"/tours/{tour['id']}/package", headers={**auth(token_b), "X-Device-Id": device_b})
    assert blocked_pkg.status_code == 409


async def test_moving_the_walk_unlocks_the_new_device_and_locks_the_old(client):
    tour, user, pid = await _bound_owner(client)
    device_b, token_b = await _sign_in_elsewhere(client, user)

    moved = await _rebind(client, token_b, pid, device_b)
    assert moved.status_code == 200
    row = await _row(client, token_b)
    assert row["device_status"] == "this_device"

    assert (await client.post("/sessions", json={"tour_id": str(tour["id"])}, headers=auth(token_b))).status_code == 201
    ok = await client.get(f"/tours/{tour['id']}/package", headers={**auth(token_b), "X-Device-Id": device_b})
    assert ok.status_code == 200
    old = await client.get(f"/tours/{tour['id']}/package", headers={**auth(token_b), "X-Device-Id": user["device"]})
    assert old.status_code == 409


async def test_can_only_move_to_the_device_you_are_signed_in_on(client):
    _, user, pid = await _bound_owner(client)
    _, token_b = await _sign_in_elsewhere(client, user)
    resp = await _rebind(client, token_b, pid, "some-other-device")
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "DEVICE_MISMATCH"


async def test_second_move_is_limited_then_allowed_after_the_cooldown(client):
    tour, user, pid = await _bound_owner(client)
    device_b, token_b = await _sign_in_elsewhere(client, user)
    assert (await _rebind(client, token_b, pid, device_b)).status_code == 200

    device_c, token_c = await _sign_in_elsewhere(client, user)
    row = await _row(client, token_c)
    assert row["device_status"] == "other_device" and row["rebind_available_at"] is not None
    refused = await _rebind(client, token_c, pid, device_c)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "REBIND_COOLDOWN"

    await _age_rebind(client, pid, days=31)
    assert (await _row(client, token_c))["rebind_available_at"] is None
    assert (await _rebind(client, token_c, pid, device_c)).status_code == 200


async def test_first_bind_and_same_device_do_not_use_the_allowance(client):
    tour = await make_tour(client)
    user = await signup(client)
    tok = user["access_token"]
    bought = await buy(client, tok, tour["id"])
    pid = bought["purchase_id"]
    assert (await _rebind(client, tok, pid, user["device"])).status_code == 200  # binds an unbound purchase
    assert (await _rebind(client, tok, pid, user["device"])).status_code == 200  # same device: no-op
    async with client.session_factory() as db:
        purchase = (await db.execute(select(Purchase).where(Purchase.id == uuid.UUID(str(pid))))).scalar_one()
    assert purchase.device_rebound_at is None and purchase.device_id == user["device"]

    # so the first real move is still available afterwards
    device_b, token_b = await _sign_in_elsewhere(client, user)
    assert (await _rebind(client, token_b, pid, device_b)).status_code == 200


async def test_consumed_walk_cannot_be_moved(client):
    tour, user, pid = await _bound_owner(client)
    tok = user["access_token"]
    session = await start_walk(client, tok, tour["id"])
    await complete_walk(client, tok, session["id"])
    device_b, token_b = await _sign_in_elsewhere(client, user)
    resp = await _rebind(client, token_b, pid, device_b)
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "TOUR_ALREADY_COMPLETED"


async def test_cannot_move_someone_elses_purchase_or_without_login(client):
    _, _, pid = await _bound_owner(client)
    stranger = await signup(client)
    resp = await _rebind(client, stranger["access_token"], pid, stranger["device"])
    assert resp.status_code == 404
    anon = await client.post(f"/purchases/{pid}/rebind-device", json={"device_identifier": "x"})
    assert anon.status_code == 401


async def test_progress_is_kept_when_moving_devices(client):
    tour, user, pid = await _bound_owner(client, stops=3)
    tok = user["access_token"]
    session = await start_walk(client, tok, tour["id"])
    from tests.helpers import arrive

    await arrive(client, tok, session["id"], tour["stop_ids"][:2])
    device_b, token_b = await _sign_in_elsewhere(client, user)
    await _rebind(client, token_b, pid, device_b)
    resumed = await client.post("/sessions", json={"tour_id": str(tour["id"])}, headers=auth(token_b))
    assert resumed.json()["id"] == session["id"] and resumed.json()["stops_visited"] == 2


async def test_refund_clears_the_binding(client):
    tour, user, pid = await _bound_owner(client)
    tok = user["access_token"]
    assert (await client.post(f"/purchases/{pid}/refund", headers=auth(tok))).status_code == 200
    async with client.session_factory() as db:
        purchase = (await db.execute(select(Purchase).where(Purchase.id == uuid.UUID(str(pid))))).scalar_one()
    assert purchase.device_id is None
