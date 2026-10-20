import uuid

from tests.factories import make_neighbourhood, make_tour
from tests.helpers import arrive, auth, buy, complete_walk, signup, start_walk


async def _finish(client, tok, tour) -> dict:
    """Buy and fully walk a tour; returns the completed session."""
    await buy(client, tok, tour["id"])
    session = await start_walk(client, tok, tour["id"])
    await arrive(client, tok, session["id"], tour["stop_ids"])
    await complete_walk(client, tok, session["id"])
    return session


async def _walker(client, tour):
    user = await signup(client)
    session = await _finish(client, user["access_token"], tour)
    return user["access_token"], session


# ---------------------------------------------------------------- ratings

async def test_rating_requires_completed_walk(client):
    tour = await make_tour(client)
    user = await signup(client)
    tok = user["access_token"]
    await buy(client, tok, tour["id"])
    resp = await client.put(f"/tours/{tour['id']}/rating", json={"rating": 5}, headers=auth(tok))
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "TOUR_NOT_COMPLETED"


async def test_rating_requires_login(client):
    tour = await make_tour(client)
    assert (await client.put(f"/tours/{tour['id']}/rating", json={"rating": 5})).status_code == 401


async def test_rating_bounds_validated(client):
    tour = await make_tour(client)
    tok, _ = await _walker(client, tour)
    for bad in (0, 6, -1):
        resp = await client.put(f"/tours/{tour['id']}/rating", json={"rating": bad}, headers=auth(tok))
        assert resp.status_code == 422


async def test_rate_then_change_rating_is_an_upsert(client):
    tour = await make_tour(client)
    tok, _ = await _walker(client, tour)
    first = await client.put(f"/tours/{tour['id']}/rating", json={"rating": 3}, headers=auth(tok))
    assert first.status_code == 200 and first.json()["my_rating"] == 3
    second = (await client.put(f"/tours/{tour['id']}/rating", json={"rating": 5}, headers=auth(tok))).json()
    assert second["my_rating"] == 5 and second["rating_count"] == 1 and second["avg_rating"] == 5.0


async def test_rating_distribution_and_average(client):
    tour = await make_tour(client)
    for stars in (5, 4, 4):
        tok, _ = await _walker(client, tour)
        await client.put(f"/tours/{tour['id']}/rating", json={"rating": stars}, headers=auth(tok))
    body = (await client.get(f"/tours/{tour['id']}/rating")).json()
    assert body["rating_count"] == 3 and body["avg_rating"] == 4.3
    assert body["my_rating"] is None
    assert {int(k): v for k, v in body["distribution"].items()} == {1: 0, 2: 0, 3: 0, 4: 2, 5: 1}


async def test_rating_hidden_tour_404(client):
    tour = await make_tour(client, published=False)
    user = await signup(client)
    resp = await client.put(f"/tours/{tour['id']}/rating", json={"rating": 4}, headers=auth(user["access_token"]))
    assert resp.status_code == 404


async def test_tour_list_and_detail_show_ratings_and_sort(client):
    low = await make_tour(client, name="Low rated")
    high = await make_tour(client, name="High rated")
    tok1, _ = await _walker(client, low)
    tok2, _ = await _walker(client, high)
    await client.put(f"/tours/{low['id']}/rating", json={"rating": 2}, headers=auth(tok1))
    await client.put(f"/tours/{high['id']}/rating", json={"rating": 5}, headers=auth(tok2))

    items = (await client.get("/tours", params={"sort": "rating"})).json()
    ids = [t["id"] for t in items]
    assert ids.index(str(high["id"])) < ids.index(str(low["id"]))
    row = next(t for t in items if t["id"] == str(high["id"]))
    assert row["avg_rating"] == 5.0 and row["rating_count"] == 1

    detail = (await client.get(f"/tours/{high['id']}", headers=auth(tok2))).json()
    assert detail["my_rating"] == 5


# ---------------------------------------------------------------- likes

async def test_like_requires_completed_walk(client):
    tour = await make_tour(client)
    user = await signup(client)
    resp = await client.post(f"/tours/{tour['id']}/like", headers=auth(user["access_token"]))
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "TOUR_NOT_COMPLETED"


async def test_like_is_idempotent_and_unlike_reports_false(client):
    tour = await make_tour(client)
    tok, _ = await _walker(client, tour)
    a = (await client.post(f"/tours/{tour['id']}/like", headers=auth(tok))).json()
    b = (await client.post(f"/tours/{tour['id']}/like", headers=auth(tok))).json()
    assert a == b == {"liked": True, "like_count": 1}
    gone = (await client.delete(f"/tours/{tour['id']}/like", headers=auth(tok))).json()
    assert gone == {"liked": False, "like_count": 0}
    again = await client.delete(f"/tours/{tour['id']}/like", headers=auth(tok))
    assert again.status_code == 200 and again.json()["liked"] is False


async def test_hidden_tour_cannot_be_liked_or_saved(client):
    tour = await make_tour(client, published=False)
    user = await signup(client)
    tok = user["access_token"]
    assert (await client.post(f"/tours/{tour['id']}/like", headers=auth(tok))).status_code == 404
    assert (await client.post("/saved-tours", json={"tour_id": str(tour["id"])}, headers=auth(tok))).status_code == 404


# ---------------------------------------------------------------- comments / reviews

async def test_comment_needs_completion_and_is_capped_at_1000(client):
    tour = await make_tour(client)
    user = await signup(client)
    path = f"/tours/{tour['id']}/comments"
    blocked = await client.post(path, json={"comment_text": "hi"}, headers=auth(user["access_token"]))
    assert blocked.status_code == 403

    tok, _ = await _walker(client, tour)
    too_long = await client.post(path, json={"comment_text": "x" * 1001}, headers=auth(tok))
    assert too_long.status_code == 422  # not a DB-CHECK 500
    ok = await client.post(path, json={"comment_text": "x" * 1000}, headers=auth(tok))
    assert ok.status_code == 201


async def test_comment_is_sanitised_and_uses_display_name(client):
    tour = await make_tour(client)
    tok, _ = await _walker(client, tour)
    resp = await client.post(
        f"/tours/{tour['id']}/comments",
        json={"comment_text": "  <b>Lovely</b> walk\x00  "},
        headers=auth(tok),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "\x00" not in body["content"] and not body["content"].startswith(" ")
    listed = (await client.get(f"/tours/{tour['id']}/comments")).json()
    assert listed[0]["user_name"] == "Test W."  # never the full name


async def test_blank_comment_rejected(client):
    tour = await make_tour(client)
    tok, _ = await _walker(client, tour)
    resp = await client.post(f"/tours/{tour['id']}/comments", json={"comment_text": "   "}, headers=auth(tok))
    assert resp.status_code == 422


async def test_hidden_tour_comments_404(client):
    tour = await make_tour(client, published=False)
    user = await signup(client)
    resp = await client.post(
        f"/tours/{tour['id']}/comments", json={"comment_text": "hi"}, headers=auth(user["access_token"])
    )
    assert resp.status_code == 404


async def test_reviews_feed_pairs_comment_with_rating(client):
    tour = await make_tour(client, name="Reviewed walk")
    other = await make_tour(client, name="Other walk")
    tok, _ = await _walker(client, tour)
    await client.put(f"/tours/{tour['id']}/rating", json={"rating": 4}, headers=auth(tok))
    await client.post(f"/tours/{tour['id']}/comments", json={"comment_text": "Great stories"}, headers=auth(tok))
    tok2, _ = await _walker(client, other)
    await client.post(f"/tours/{other['id']}/comments", json={"comment_text": "Fine"}, headers=auth(tok2))

    feed = (await client.get("/reviews")).json()
    mine = next(r for r in feed if r["tour_id"] == str(tour["id"]))
    assert mine["rating"] == 4 and mine["content"] == "Great stories"
    assert mine["tour_name"] == "Reviewed walk" and mine["user_name"] == "Test W."
    unrated = next(r for r in feed if r["tour_id"] == str(other["id"]))
    assert unrated["rating"] is None

    only = (await client.get("/reviews", params={"tour_id": str(tour["id"])})).json()
    assert [r["tour_id"] for r in only] == [str(tour["id"])]
    assert len((await client.get("/reviews", params={"limit": 1})).json()) == 1


async def test_reviews_exclude_deleted_comments_and_hidden_tours(client):
    tour = await make_tour(client)
    tok, _ = await _walker(client, tour)
    created = (
        await client.post(f"/tours/{tour['id']}/comments", json={"comment_text": "oops"}, headers=auth(tok))
    ).json()
    cid = created["id"]
    assert (await client.delete(f"/tours/{tour['id']}/comments/{cid}", headers=auth(tok))).status_code == 204
    feed = (await client.get("/reviews", params={"tour_id": str(tour["id"])})).json()
    assert feed == []


# ---------------------------------------------------------------- me/stats + passport

async def test_stats_zero_for_new_user_and_requires_login(client):
    assert (await client.get("/me/stats")).status_code == 401
    user = await signup(client)
    body = (await client.get("/me/stats", headers=auth(user["access_token"]))).json()
    assert body == {
        "walks_completed": 0, "distance_km": 0.0, "stops_visited": 0,
        "listening_minutes": 0, "neighbourhoods_stamped": 0,
    }


async def test_stats_add_up_completed_walks_only(client):
    hood = await make_neighbourhood(client, "Indiranagar")
    t1 = await make_tour(client, neighbourhood_id=hood.id, stops=3)
    t2 = await make_tour(client, neighbourhood_id=hood.id, stops=2)
    t3 = await make_tour(client, neighbourhood_id=hood.id)
    user = await signup(client)
    tok = user["access_token"]
    await _finish(client, tok, t1)
    await _finish(client, tok, t2)
    await buy(client, tok, t3["id"])
    await start_walk(client, tok, t3["id"])  # in progress: must not count

    body = (await client.get("/me/stats", headers=auth(tok))).json()
    assert body["walks_completed"] == 2
    assert body["distance_km"] == 4.0
    assert body["stops_visited"] == 5
    assert body["listening_minutes"] == 90
    assert body["neighbourhoods_stamped"] == 1


async def test_passport_stamps_and_ordering(client):
    a = await make_neighbourhood(client, "Aaa Hood")
    b = await make_neighbourhood(client, "Bbb Hood")
    await make_tour(client, neighbourhood_id=a.id)
    tb1 = await make_tour(client, neighbourhood_id=b.id)
    await make_tour(client, neighbourhood_id=b.id)
    await make_tour(client, neighbourhood_id=b.id, published=False)  # hidden: not counted
    user = await signup(client)
    tok = user["access_token"]
    await _finish(client, tok, tb1)

    body = (await client.get("/me/passport", headers=auth(tok))).json()
    mine = {s["neighbourhood"]["id"]: s for s in body["stamps"]}
    sb, sa = mine[str(b.id)], mine[str(a.id)]
    assert sb["stamped"] and sb["tours_total"] == 2 and sb["tours_completed"] == 1 and sb["stamped_at"]
    assert not sa["stamped"] and sa["tours_total"] == 1 and sa["stamped_at"] is None
    assert body["stamps_collected"] == 1 and body["total_neighbourhoods"] == len(body["stamps"])
    names = [s["neighbourhood"]["name"] for s in body["stamps"]]
    assert names.index("Bbb Hood") < names.index("Aaa Hood")  # stamped first


async def test_passport_requires_login(client):
    assert (await client.get("/me/passport")).status_code == 401


# ---------------------------------------------------------------- walk-complete summary

async def test_session_summary_first_walk_in_hood_earns_stamp_second_does_not(client):
    hood = await make_neighbourhood(client, "Basavanagudi")
    t1 = await make_tour(client, neighbourhood_id=hood.id, stops=3)
    t2 = await make_tour(client, neighbourhood_id=hood.id, stops=2)
    user = await signup(client)
    tok = user["access_token"]
    s1 = await _finish(client, tok, t1)
    s2 = await _finish(client, tok, t2)

    first = (await client.get(f"/sessions/{s1['id']}/summary", headers=auth(tok))).json()
    assert first["completed"] and first["stamp_earned"] is True
    assert first["stop_count"] == 3 and first["stops_visited"] == 3
    assert first["neighbourhood"]["name"] == "Basavanagudi"
    second = (await client.get(f"/sessions/{s2['id']}/summary", headers=auth(tok))).json()
    assert second["stamp_earned"] is False


async def test_session_summary_reflects_reactions(client):
    tour = await make_tour(client)
    tok, session = await _walker(client, tour)
    before = (await client.get(f"/sessions/{session['id']}/summary", headers=auth(tok))).json()
    assert before["my_rating"] is None and not before["liked"] and not before["commented"]

    await client.put(f"/tours/{tour['id']}/rating", json={"rating": 4}, headers=auth(tok))
    await client.post(f"/tours/{tour['id']}/like", headers=auth(tok))
    await client.post(f"/tours/{tour['id']}/comments", json={"comment_text": "nice"}, headers=auth(tok))
    after = (await client.get(f"/sessions/{session['id']}/summary", headers=auth(tok))).json()
    assert after["my_rating"] == 4 and after["avg_rating"] == 4.0 and after["rating_count"] == 1
    assert after["liked"] is True and after["commented"] is True


async def test_session_summary_is_private_to_owner(client):
    tour = await make_tour(client)
    _, session = await _walker(client, tour)
    stranger = await signup(client)
    resp = await client.get(f"/sessions/{session['id']}/summary", headers=auth(stranger["access_token"]))
    assert resp.status_code == 404
    missing = await client.get(f"/sessions/{uuid.uuid4()}/summary", headers=auth(stranger["access_token"]))
    assert missing.status_code == 404
    assert (await client.get(f"/sessions/{session['id']}/summary")).status_code == 401
