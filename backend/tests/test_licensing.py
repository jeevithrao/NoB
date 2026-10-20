"""The one-lifetime-playback licence, device binding and walk lifecycle."""
import uuid
from datetime import datetime, timezone

from tests.factories import make_tour
from tests.helpers import arrive, auth, buy, complete_walk, login, signup, start_walk


def _event(stop_id, kind="arrived", event_id=None):
    return {
        "client_event_id": str(event_id or uuid.uuid4()),
        "stop_id": str(stop_id),
        "event_type": kind,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }


async def _owner(client, tour):
    user = await signup(client)
    bought = await buy(client, user["access_token"], tour["id"])
    return user, bought


# ---------------------------------------------------------------- starting a walk

async def test_cannot_start_walk_without_purchase(client):
    tour = await make_tour(client)
    user = await signup(client)
    resp = await client.post("/sessions", json={"tour_id": str(tour["id"])}, headers=auth(user["access_token"]))
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "TOUR_NOT_OWNED"


async def test_cannot_start_walk_on_unpublished_tour(client):
    tour = await make_tour(client, published=False)
    user = await signup(client)
    resp = await client.post("/sessions", json={"tour_id": str(tour["id"])}, headers=auth(user["access_token"]))
    assert resp.status_code == 404


async def test_someone_elses_purchase_does_not_unlock_the_tour(client):
    tour = await make_tour(client)
    await _owner(client, tour)
    thief = await signup(client)
    resp = await client.post("/sessions", json={"tour_id": str(tour["id"])}, headers=auth(thief["access_token"]))
    assert resp.status_code == 403


async def test_starting_twice_resumes_the_same_session(client):
    tour = await make_tour(client)
    user, _ = await _owner(client, tour)
    tok = user["access_token"]
    first = await start_walk(client, tok, tour["id"])
    second = await start_walk(client, tok, tour["id"])
    assert first["id"] == second["id"]


# ---------------------------------------------------------------- progress / resume

async def test_progress_survives_interruption_and_does_not_consume_licence(client):
    tour = await make_tour(client, stops=3)
    user, _ = await _owner(client, tour)
    tok = user["access_token"]
    session = await start_walk(client, tok, tour["id"])
    body = await arrive(client, tok, session["id"], tour["stop_ids"][:2])
    assert body["accepted"] == 2 and body["session"]["stops_visited"] == 2

    resumed = await start_walk(client, tok, tour["id"])  # app killed, user reopens
    assert resumed["id"] == session["id"] and resumed["stops_visited"] == 2 and not resumed["completed"]

    await arrive(client, tok, session["id"], tour["stop_ids"][2:])
    done = await complete_walk(client, tok, session["id"])
    assert done["completed"] and done["stops_visited"] == 3


async def test_replayed_event_batch_is_deduplicated(client):
    tour = await make_tour(client, stops=2)
    user, _ = await _owner(client, tour)
    tok = user["access_token"]
    session = await start_walk(client, tok, tour["id"])
    batch = {"events": [_event(tour["stop_ids"][0]), _event(tour["stop_ids"][1])]}
    first = (await client.post(f"/sessions/{session['id']}/events/batch", json=batch, headers=auth(tok))).json()
    again = (await client.post(f"/sessions/{session['id']}/events/batch", json=batch, headers=auth(tok))).json()
    assert (first["accepted"], first["duplicate"]) == (2, 0)
    assert (again["accepted"], again["duplicate"]) == (0, 2)
    assert again["session"]["stops_visited"] == 2


async def test_stops_visited_counts_distinct_stops(client):
    tour = await make_tour(client, stops=3)
    user, _ = await _owner(client, tour)
    tok = user["access_token"]
    session = await start_walk(client, tok, tour["id"])
    stop = tour["stop_ids"][0]
    batch = {"events": [_event(stop), _event(stop), _event(stop, "audio_started")]}
    body = (await client.post(f"/sessions/{session['id']}/events/batch", json=batch, headers=auth(tok))).json()
    assert body["accepted"] == 3 and body["session"]["stops_visited"] == 1


async def test_events_for_a_stop_of_another_tour_are_rejected(client):
    tour = await make_tour(client, stops=2)
    other = await make_tour(client, stops=2)
    user, _ = await _owner(client, tour)
    tok = user["access_token"]
    session = await start_walk(client, tok, tour["id"])
    batch = {"events": [_event(other["stop_ids"][0])]}
    resp = await client.post(f"/sessions/{session['id']}/events/batch", json=batch, headers=auth(tok))
    assert resp.status_code == 422 and resp.json()["error"]["code"] == "INVALID_STOP"
    refreshed = await start_walk(client, tok, tour["id"])
    assert refreshed["stops_visited"] == 0


async def test_another_user_cannot_post_events_or_complete_my_session(client):
    tour = await make_tour(client)
    user, _ = await _owner(client, tour)
    session = await start_walk(client, user["access_token"], tour["id"])
    stranger = await signup(client)
    stok = stranger["access_token"]
    batch = {"events": [_event(tour["stop_ids"][0])]}
    assert (await client.post(f"/sessions/{session['id']}/events/batch", json=batch, headers=auth(stok))).status_code == 404
    assert (await client.post(f"/sessions/{session['id']}/complete", headers=auth(stok))).status_code == 404


# ---------------------------------------------------------------- consuming the licence

async def test_completion_consumes_the_licence(client):
    tour = await make_tour(client)
    user, bought = await _owner(client, tour)
    tok = user["access_token"]
    session = await start_walk(client, tok, tour["id"])
    await arrive(client, tok, session["id"], tour["stop_ids"])
    await complete_walk(client, tok, session["id"])

    replay = await client.post("/sessions", json={"tour_id": str(tour["id"])}, headers=auth(tok))
    assert replay.status_code == 403 and replay.json()["error"]["code"] == "TOUR_ALREADY_COMPLETED"

    locked = await client.post(
        f"/sessions/{session['id']}/events/batch", json={"events": [_event(tour["stop_ids"][0])]}, headers=auth(tok)
    )
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "SESSION_LOCKED"

    purchase = (await client.get(f"/purchases/{bought['purchase_id']}", headers=auth(tok))).json()
    assert purchase["status"] == "completed"


async def test_completing_twice_is_idempotent(client):
    tour = await make_tour(client)
    user, _ = await _owner(client, tour)
    tok = user["access_token"]
    session = await start_walk(client, tok, tour["id"])
    first = await complete_walk(client, tok, session["id"])
    second = await complete_walk(client, tok, session["id"])
    assert first["completed_at"] == second["completed_at"]


async def test_buying_again_after_completion_is_refused(client):
    """Documented limitation: one completed walk per user+tour, so a rebuy is blocked."""
    tour = await make_tour(client)
    user, _ = await _owner(client, tour)
    tok = user["access_token"]
    session = await start_walk(client, tok, tour["id"])
    await complete_walk(client, tok, session["id"])
    resp = await client.post("/purchases", json={"tour_id": str(tour["id"])}, headers=auth(tok))
    assert resp.status_code == 409


# ---------------------------------------------------------------- device binding

async def test_package_requires_ownership_and_device_header(client):
    tour = await make_tour(client)
    user = await signup(client)
    tok = user["access_token"]
    no_header = await client.get(f"/tours/{tour['id']}/package", headers=auth(tok))
    assert no_header.status_code == 422
    unowned = await client.get(f"/tours/{tour['id']}/package", headers={**auth(tok), "X-Device-Id": user["device"]})
    assert unowned.status_code == 403 and unowned.json()["error"]["code"] == "TOUR_NOT_OWNED"


async def test_package_for_owner_has_ordered_stops_with_signed_audio(client):
    tour = await make_tour(client, stops=3)
    user, _ = await _owner(client, tour)
    resp = await client.get(
        f"/tours/{tour['id']}/package", headers={**auth(user["access_token"]), "X-Device-Id": user["device"]}
    )
    assert resp.status_code == 200
    stops = resp.json()["stops"]
    assert [s["order_index"] for s in stops] == [1, 2, 3]
    assert all("signature" in s["audio_url"] or "sig" in s["audio_url"] for s in stops)


async def test_bind_device_then_second_device_is_rejected(client):
    tour = await make_tour(client)
    user, bought = await _owner(client, tour)
    tok = user["access_token"]
    pid = bought["purchase_id"]
    bound = await client.post(f"/purchases/{pid}/bind-device", json={"device_identifier": "phone-A"}, headers=auth(tok))
    assert bound.status_code == 200
    again = await client.post(f"/purchases/{pid}/bind-device", json={"device_identifier": "phone-A"}, headers=auth(tok))
    assert again.status_code == 200  # same device: idempotent

    other = await client.post(f"/purchases/{pid}/bind-device", json={"device_identifier": "phone-B"}, headers=auth(tok))
    assert other.status_code == 409 and other.json()["error"]["code"] == "BOUND_TO_OTHER_DEVICE"
    pkg = await client.get(f"/tours/{tour['id']}/package", headers={**auth(tok), "X-Device-Id": "phone-B"})
    assert pkg.status_code == 409 and pkg.json()["error"]["code"] == "BOUND_TO_OTHER_DEVICE"
    ok = await client.get(f"/tours/{tour['id']}/package", headers={**auth(tok), "X-Device-Id": "phone-A"})
    assert ok.status_code == 200


async def test_bind_device_only_for_own_completed_purchase(client):
    tour = await make_tour(client)
    _, bought = await _owner(client, tour)
    stranger = await signup(client)
    resp = await client.post(
        f"/purchases/{bought['purchase_id']}/bind-device",
        json={"device_identifier": "x"},
        headers=auth(stranger["access_token"]),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------- single active session

async def test_old_device_token_dies_mid_walk_but_progress_is_kept(client):
    tour = await make_tour(client, stops=2)
    user, _ = await _owner(client, tour)
    old = user["access_token"]
    session = await start_walk(client, old, tour["id"])
    await arrive(client, old, session["id"], tour["stop_ids"][:1])

    fresh = await login(client, user["email"], user["password"], "second-phone")
    assert fresh.status_code == 200
    new = fresh.json()["access_token"]

    kicked = await client.post(
        f"/sessions/{session['id']}/events/batch", json={"events": [_event(tour["stop_ids"][1])]}, headers=auth(old)
    )
    assert kicked.status_code == 401
    resumed = await client.post("/sessions", json={"tour_id": str(tour["id"])}, headers=auth(new))
    assert resumed.json()["id"] == session["id"] and resumed.json()["stops_visited"] == 1


async def test_session_endpoints_require_login(client):
    sid = uuid.uuid4()
    assert (await client.post("/sessions", json={"tour_id": str(uuid.uuid4())})).status_code == 401
    assert (await client.post(f"/sessions/{sid}/complete")).status_code == 401
    assert (await client.post(f"/sessions/{sid}/events/batch", json={"events": []})).status_code == 401
