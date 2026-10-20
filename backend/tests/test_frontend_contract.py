"""Fields and behaviours the React frontend relies on (docs/FRONTEND_INTEGRATION.md)."""
import re

from sqlalchemy import select, update

from app.models import Stop, User
from tests.factories import make_admin, make_neighbourhood, make_tour
from tests.helpers import arrive, auth, buy, complete_walk, new_device, new_email, signup, start_walk

BOOKING_REF = re.compile(r"^NOB-[0-9A-Z]{8}$")


async def _set_stop_teasers(client, tour):
    async with client.session_factory() as db:
        for i, stop_id in enumerate(tour["stop_ids"], start=1):
            await db.execute(
                update(Stop).where(Stop.id == stop_id).values(blurb=f"Teaser {i}", icon="🛕", narrative_text="SECRET NARRATION")
            )
        await db.commit()


# ---------------------------------------------------------------- walk detail

async def test_detail_has_presentation_fields_and_public_stop_preview(client):
    hood = await make_neighbourhood(client, "Malleshwaram", description="Old Bangalore.", emoji="🌸", tagline="Old Bangalore")
    tour = await make_tour(
        client,
        neighbourhood_id=hood.id,
        theme="Heritage",
        difficulty="Moderate",
        start_point="Sampige Road Metro Gate",
        tags=["Morning recommended"],
        preview_audio_title="Silk weavers",
        stops=3,
    )
    await _set_stop_teasers(client, tour)
    body = (await client.get(f"/tours/{tour['id']}")).json()  # anonymous
    assert body["theme"] == "Heritage" and body["difficulty"] == "Moderate"
    assert body["start_point"] == "Sampige Road Metro Gate" and body["tags"] == ["Morning recommended"]
    assert body["preview_audio_title"] == "Silk weavers"
    assert body["neighbourhood_description"] == "Old Bangalore."
    assert body["neighbourhood"]["emoji"] == "🌸"
    assert body["stop_count"] == 3
    preview = body["stops_preview"]
    assert [s["order_index"] for s in preview] == [1, 2, 3]
    assert preview[0] == {"order_index": 1, "name": "Stop 1", "blurb": "Teaser 1", "icon": "🛕"}


async def test_stop_preview_never_leaks_paid_content(client):
    tour = await make_tour(client, stops=2)
    await _set_stop_teasers(client, tour)
    resp = await client.get(f"/tours/{tour['id']}")
    assert "SECRET NARRATION" not in resp.text
    for stop in resp.json()["stops_preview"]:
        assert set(stop) == {"order_index", "name", "blurb", "icon"}  # no audio, narration or coordinates


async def test_numbers_are_json_numbers_not_strings(client):
    tour = await make_tour(client)
    user = await signup(client)
    await buy(client, user["access_token"], tour["id"])
    listed = (await client.get("/tours")).json()[0]
    assert isinstance(listed["distance_km"], float)
    pkg = (
        await client.get(
            f"/tours/{tour['id']}/package", headers={**auth(user["access_token"]), "X-Device-Id": user["device"]}
        )
    ).json()
    assert isinstance(pkg["stops"][0]["lat"], float) and isinstance(pkg["stops"][0]["lng"], float)


# ---------------------------------------------------------------- explore filters

async def test_filters_multi_neighbourhood_theme_and_duration(client):
    a = await make_neighbourhood(client, "Alpha")
    b = await make_neighbourhood(client, "Bravo")
    c = await make_neighbourhood(client, "Charlie")
    ta = await make_tour(client, name="A walk", neighbourhood_id=a.id, theme="Heritage", duration_min=45)
    tb = await make_tour(client, name="B walk", neighbourhood_id=b.id, theme="Nature", duration_min=75)
    tc = await make_tour(client, name="C walk", neighbourhood_id=c.id, theme="Heritage", duration_min=120)

    async def ids(**params):
        resp = await client.get("/tours", params=params)
        assert resp.status_code == 200, resp.text
        return {t["id"] for t in resp.json()}

    both = await ids(neighbourhood=[a.slug, b.slug])
    assert both == {str(ta["id"]), str(tb["id"])}
    mixed = await ids(neighbourhood=[a.slug, str(c.id)])
    assert mixed == {str(ta["id"]), str(tc["id"])}
    assert await ids(theme="Heritage") == {str(ta["id"]), str(tc["id"])}
    assert await ids(theme=["Nature", "Heritage"]) >= {str(ta["id"]), str(tb["id"]), str(tc["id"])}
    assert await ids(max_duration=59) >= {str(ta["id"])} and str(tb["id"]) not in await ids(max_duration=59)
    middle = await ids(min_duration=60, max_duration=90)
    assert str(tb["id"]) in middle and str(ta["id"]) not in middle and str(tc["id"]) not in middle
    assert str(tc["id"]) in await ids(min_duration=91)


# ---------------------------------------------------------------- admin + validation envelope

async def test_admin_can_set_new_tour_and_stop_fields(client):
    admin = await make_admin(client)
    tok = admin["access_token"]
    created = await client.post(
        "/admin/tours",
        json={"name": "T", "theme": "Culture", "difficulty": "Easy", "start_point": "Arch", "tags": ["Easy pace"], "preview_audio_title": "Sample"},
        headers=auth(tok),
    )
    assert created.status_code == 201, created.text
    tour_id = created.json()["id"]
    assert created.json()["difficulty"] == "Easy" and created.json()["tags"] == ["Easy pace"]
    stop = await client.post(
        f"/admin/tours/{tour_id}/stops",
        json={"order_index": 1, "name": "S", "lat": 12.9, "lng": 77.5, "audio_filename": "x.mp3", "blurb": "Teaser", "icon": "🏛️"},
        headers=auth(tok),
    )
    assert stop.status_code == 201 and stop.json()["blurb"] == "Teaser" and stop.json()["icon"] == "🏛️"
    updated = await client.put(f"/admin/tours/{tour_id}", json={"difficulty": "Hard"}, headers=auth(tok))
    assert updated.json()["difficulty"] == "Hard"


async def test_invalid_difficulty_uses_the_error_envelope(client):
    admin = await make_admin(client)
    resp = await client.post("/admin/tours", json={"name": "T", "difficulty": "Impossible"}, headers=auth(admin["access_token"]))
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["code"] == "VALIDATION_ERROR" and "difficulty" in err["fields"] and "detail" not in resp.json()


async def test_validation_error_lists_every_bad_field(client):
    resp = await client.post("/auth/signup", json={"email": "not-an-email", "password": "x", "device_identifier": "d", "accepted_terms": True})
    assert resp.status_code == 422
    fields = resp.json()["error"]["fields"]
    assert "email" in fields and "password" in fields


# ---------------------------------------------------------------- signup consent

async def test_signup_requires_terms_acceptance(client):
    body = {"email": new_email(), "password": "correct-horse-1", "device_identifier": new_device()}
    missing = await client.post("/auth/signup", json=body)
    assert missing.status_code == 422 and "accepted_terms" in missing.json()["error"]["fields"]
    refused = await client.post("/auth/signup", json={**body, "accepted_terms": False})
    assert refused.status_code == 422 and "accepted_terms" in refused.json()["error"]["fields"]


async def test_signup_records_consent_evidence(client):
    email = new_email()
    resp = await client.post(
        "/auth/signup",
        json={"email": email, "password": "correct-horse-1", "device_identifier": new_device(), "accepted_terms": True, "marketing_opt_in": True},
    )
    assert resp.status_code == 201
    async with client.session_factory() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
    assert user.terms_accepted_at is not None and user.terms_version and user.marketing_opt_in is True
    default = await signup(client)
    async with client.session_factory() as db:
        other = (await db.execute(select(User).where(User.email == default["email"]))).scalar_one()
    assert other.marketing_opt_in is False  # opt-in is never assumed


# ---------------------------------------------------------------- free walks

async def test_free_walk_claim_appears_in_bookings_and_can_be_walked(client):
    tour = await make_tour(client, is_free=True, stops=2)
    user = await signup(client)
    tok = user["access_token"]
    claim = await client.post("/purchases", json={"tour_id": str(tour["id"])}, headers=auth(tok))
    assert claim.status_code == 201
    assert claim.json()["status"] == "completed" and claim.json()["gateway_config"] == {"free": True}

    (row,) = (await client.get("/purchases", headers=auth(tok))).json()
    assert row["amount_paise"] == 0 and row["walk_status"] == "not_started" and BOOKING_REF.match(row["booking_ref"])

    again = await client.post("/purchases", json={"tour_id": str(tour["id"])}, headers=auth(tok))
    assert again.status_code == 409 and again.json()["error"]["code"] == "TOUR_ALREADY_OWNED"

    session = await start_walk(client, tok, tour["id"])
    await arrive(client, tok, session["id"], tour["stop_ids"])
    await complete_walk(client, tok, session["id"])
    replay = await client.post("/sessions", json={"tour_id": str(tour["id"])}, headers=auth(tok))
    assert replay.status_code == 403 and replay.json()["error"]["code"] == "TOUR_ALREADY_COMPLETED"


async def test_free_walk_still_works_without_a_claim(client):
    """Older clients that skip the claim can still walk a free tour."""
    tour = await make_tour(client, is_free=True)
    user = await signup(client)
    session = await start_walk(client, user["access_token"], tour["id"])
    assert session["id"]


async def test_free_walk_can_be_cancelled_before_starting(client):
    tour = await make_tour(client, is_free=True)
    user = await signup(client)
    tok = user["access_token"]
    claim = (await client.post("/purchases", json={"tour_id": str(tour["id"])}, headers=auth(tok))).json()
    refunded = await client.post(f"/purchases/{claim['purchase_id']}/refund", headers=auth(tok))
    assert refunded.status_code == 200 and refunded.json()["status"] == "refunded"
    reclaim = await client.post("/purchases", json={"tour_id": str(tour["id"])}, headers=auth(tok))
    assert reclaim.status_code == 201


# ---------------------------------------------------------------- bookings / passport / stats

async def test_booking_row_has_ref_completed_at_and_my_rating(client):
    tour = await make_tour(client, theme="Heritage")
    user = await signup(client)
    tok = user["access_token"]
    await buy(client, tok, tour["id"])
    (before,) = (await client.get("/purchases", params={"tab": "upcoming"}, headers=auth(tok))).json()
    assert BOOKING_REF.match(before["booking_ref"]) and before["completed_at"] is None and before["my_rating"] is None
    assert before["tour"]["theme"] == "Heritage"

    session = await start_walk(client, tok, tour["id"])
    await arrive(client, tok, session["id"], tour["stop_ids"])
    await complete_walk(client, tok, session["id"])
    await client.put(f"/tours/{tour['id']}/rating", json={"rating": 4}, headers=auth(tok))
    (after,) = (await client.get("/purchases", params={"tab": "past"}, headers=auth(tok))).json()
    assert after["completed_at"] and after["my_rating"] == 4 and after["booking_ref"] == before["booking_ref"]


async def test_booking_refs_are_unique(client):
    user = await signup(client)
    refs = set()
    for _ in range(5):
        tour = await make_tour(client)
        await buy(client, user["access_token"], tour["id"])
    for row in (await client.get("/purchases", headers=auth(user["access_token"]))).json():
        refs.add(row["booking_ref"])
    assert len(refs) == 5


async def test_passport_lists_empty_areas_and_walk_name(client):
    walked = await make_neighbourhood(client, "Walked Hood", emoji="🌸")
    empty = await make_neighbourhood(client, "Empty Hood", emoji="☕")
    tour = await make_tour(client, name="The Silk Walk", neighbourhood_id=walked.id)
    user = await signup(client)
    tok = user["access_token"]
    await buy(client, tok, tour["id"])
    session = await start_walk(client, tok, tour["id"])
    await complete_walk(client, tok, session["id"])

    stamps = {s["neighbourhood"]["id"]: s for s in (await client.get("/me/passport", headers=auth(tok))).json()["stamps"]}
    assert stamps[str(walked.id)]["walk_name"] == "The Silk Walk" and stamps[str(walked.id)]["emoji"] == "🌸"
    assert stamps[str(empty.id)]["stamped"] is False and stamps[str(empty.id)]["walk_name"] is None

    trimmed = (await client.get("/me/passport", params={"include_empty": "false"}, headers=auth(tok))).json()["stamps"]
    assert str(empty.id) not in {s["neighbourhood"]["id"] for s in trimmed}


async def test_stats_count_reviews(client):
    t1, t2 = await make_tour(client), await make_tour(client)
    user = await signup(client)
    tok = user["access_token"]
    for tour in (t1, t2):
        await buy(client, tok, tour["id"])
        session = await start_walk(client, tok, tour["id"])
        await complete_walk(client, tok, session["id"])
    await client.put(f"/tours/{t1['id']}/rating", json={"rating": 5}, headers=auth(tok))
    assert (await client.get("/me/stats", headers=auth(tok))).json()["reviews_count"] == 1


async def test_neighbourhood_tagline_and_emoji_roundtrip(client):
    admin = await make_admin(client)
    tok = admin["access_token"]
    created = await client.post(
        "/admin/neighbourhoods", json={"name": "Tagline Town", "tagline": "Old Bangalore", "emoji": "🌸"}, headers=auth(tok)
    )
    assert created.status_code == 201
    got = (await client.get(f"/neighbourhoods/{created.json()['slug']}")).json()
    assert got["tagline"] == "Old Bangalore" and got["emoji"] == "🌸" and isinstance(got["centroid_lat"], (float, type(None)))
