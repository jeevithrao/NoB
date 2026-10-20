import uuid

import pytest

from tests.factories import make_admin, make_neighbourhood, make_tour
from tests.helpers import auth, buy, signup


def ids(resp):
    return [t["id"] for t in resp.json()]


async def test_list_returns_only_published_tours_in_the_city(client):
    shown = await make_tour(client, name="Shown")
    await make_tour(client, name="Draft", published=False)
    resp = await client.get("/tours")
    assert resp.status_code == 200 and ids(resp) == [str(shown["id"])]
    assert (await client.get("/tours", params={"city": "Mysuru"})).json() == []


async def test_list_includes_neighbourhood_and_flags(client):
    hood = await make_neighbourhood(client, "Malleshwaram")
    await make_tour(client, neighbourhood_id=hood.id, is_featured=True)
    item = (await client.get("/tours")).json()[0]
    assert item["neighbourhood"]["name"] == "Malleshwaram" and item["neighbourhood"]["slug"] == hood.slug
    assert item["is_featured"] is True and item["status"] == "not_purchased"


async def test_search_matches_name_description_and_neighbourhood(client):
    hood = await make_neighbourhood(client, "Basavanagudi")
    a = await make_tour(client, name="Temple Trail", description="old stones")
    b = await make_tour(client, name="Market Walk", description="spices and flowers")
    c = await make_tour(client, name="Park Walk", description="trees", neighbourhood_id=hood.id)
    assert ids(await client.get("/tours", params={"q": "temple"})) == [str(a["id"])]
    assert ids(await client.get("/tours", params={"q": "FLOWERS"})) == [str(b["id"])]
    assert ids(await client.get("/tours", params={"q": "basava"})) == [str(c["id"])]
    assert (await client.get("/tours", params={"q": "nothing-like-this"})).json() == []


@pytest.mark.parametrize("term", ["%", "_", "100%", "a_b", "\\"])
async def test_search_treats_wildcards_literally(client, term):
    await make_tour(client, name="Plain Walk")
    resp = await client.get("/tours", params={"q": term})
    assert resp.status_code == 200 and resp.json() == []  # '%' must not match everything


async def test_filter_by_neighbourhood_slug_or_id(client):
    one = await make_neighbourhood(client, "Indiranagar")
    two = await make_neighbourhood(client, "Jayanagar")
    a = await make_tour(client, neighbourhood_id=one.id)
    await make_tour(client, neighbourhood_id=two.id)
    assert ids(await client.get("/tours", params={"neighbourhood": one.slug})) == [str(a["id"])]
    assert ids(await client.get("/tours", params={"neighbourhood": str(one.id)})) == [str(a["id"])]
    assert (await client.get("/tours", params={"neighbourhood": "no-such-area"})).json() == []


async def test_price_and_free_filters(client):
    free = await make_tour(client, is_free=True)
    cheap = await make_tour(client, price_paise=9900)
    dear = await make_tour(client, price_paise=49900)
    assert ids(await client.get("/tours", params={"free": "true"})) == [str(free["id"])]
    assert set(ids(await client.get("/tours", params={"free": "false"}))) == {str(cheap["id"]), str(dear["id"])}
    assert ids(await client.get("/tours", params={"min_price": 20000})) == [str(dear["id"])]
    assert set(ids(await client.get("/tours", params={"max_price": 9900}))) == {str(free["id"]), str(cheap["id"])}


async def test_sorting(client):
    cheap = await make_tour(client, price_paise=9900, duration_min=90)
    dear = await make_tour(client, price_paise=49900, duration_min=20)
    asc = ids(await client.get("/tours", params={"sort": "price_asc"}))
    assert asc == [str(cheap["id"]), str(dear["id"])]
    assert ids(await client.get("/tours", params={"sort": "price_desc"})) == asc[::-1]
    assert ids(await client.get("/tours", params={"sort": "duration"})) == [str(dear["id"]), str(cheap["id"])]


async def test_popular_sort_orders_by_likes(client):
    quiet = await make_tour(client, name="Quiet")
    loved = await make_tour(client, name="Loved")
    from app.models import TourLike

    for _ in range(2):  # likes need a completed walk via the API, so seed them directly
        user = await signup(client)
        async with client.session_factory() as db:
            db.add(TourLike(user_id=uuid.UUID(user["user"]["id"]), tour_id=loved["id"]))
            await db.commit()
    assert quiet["id"]
    resp = await client.get("/tours", params={"sort": "popular"})
    assert ids(resp)[0] == str(loved["id"]) and resp.json()[0]["like_count"] == 2


async def test_pagination_is_stable_and_complete(client):
    made = [await make_tour(client) for _ in range(5)]
    page1 = ids(await client.get("/tours", params={"limit": 2, "offset": 0}))
    page2 = ids(await client.get("/tours", params={"limit": 2, "offset": 2}))
    page3 = ids(await client.get("/tours", params={"limit": 2, "offset": 4}))
    assert len(page1) == 2 and len(page2) == 2 and len(page3) == 1
    assert set(page1 + page2 + page3) == {str(m["id"]) for m in made}


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"sort": "bogus"}, {"min_price": -5}])
async def test_bad_query_parameters_are_rejected(client, params):
    assert (await client.get("/tours", params=params)).status_code == 422


async def test_featured_endpoint(client):
    star = await make_tour(client, is_featured=True)
    await make_tour(client)
    await make_tour(client, is_featured=True, published=False)
    resp = await client.get("/tours/featured")
    assert resp.status_code == 200 and ids(resp) == [str(star["id"])]


async def test_status_in_listing_follows_the_user(client):
    tour = await make_tour(client)
    user = await signup(client)
    assert (await client.get("/tours", headers=auth(user["access_token"]))).json()[0]["status"] == "not_purchased"
    await buy(client, user["access_token"], tour["id"])
    assert (await client.get("/tours", headers=auth(user["access_token"]))).json()[0]["status"] == "purchased"
    other = await signup(client)
    assert (await client.get("/tours", headers=auth(other["access_token"]))).json()[0]["status"] == "not_purchased"


async def test_detail_has_content_fields_and_signed_preview(client):
    tour = await make_tour(
        client,
        gallery_images=["a.jpg", "b.jpg"],
        includes=["Audio guide", "Offline map"],
        languages=["English", "Kannada"],
        preview_audio_filename="preview/sample.mp3",
    )
    detail = (await client.get(f"/tours/{tour['id']}")).json()
    assert detail["gallery_images"] == ["a.jpg", "b.jpg"] and detail["languages"] == ["English", "Kannada"]
    assert detail["includes"] == ["Audio guide", "Offline map"] and detail["stop_count"] == 3
    assert "/media/audio/preview/sample.mp3?exp=" in detail["preview_audio_url"] and "sig=" in detail["preview_audio_url"]


async def test_detail_of_hidden_or_missing_tour_is_404(client):
    hidden = await make_tour(client, published=False)
    assert (await client.get(f"/tours/{hidden['id']}")).status_code == 404
    assert (await client.get(f"/tours/{uuid.uuid4()}")).status_code == 404


# ------------------------------------------------------------------ neighbourhoods

async def test_neighbourhood_list_counts_only_published_tours(client):
    full = await make_neighbourhood(client, "Malleshwaram")
    empty = await make_neighbourhood(client, "Hebbal")
    await make_tour(client, neighbourhood_id=full.id)
    await make_tour(client, neighbourhood_id=full.id, published=False)
    resp = await client.get("/neighbourhoods")
    assert [(n["name"], n["tour_count"]) for n in resp.json()] == [("Malleshwaram", 1)]
    everything = await client.get("/neighbourhoods", params={"include_empty": "true"})
    assert {n["name"] for n in everything.json()} == {"Malleshwaram", "Hebbal"}
    assert empty.name == "Hebbal"


async def test_neighbourhood_detail_by_slug_and_id_with_user_status(client):
    hood = await make_neighbourhood(client, "Malleshwaram")
    tour = await make_tour(client, neighbourhood_id=hood.id)
    user = await signup(client)
    await buy(client, user["access_token"], tour["id"])
    for key in (hood.slug, str(hood.id)):
        resp = await client.get(f"/neighbourhoods/{key}", headers=auth(user["access_token"]))
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Malleshwaram" and body["tour_count"] == 1
        assert body["tours"][0]["id"] == str(tour["id"]) and body["tours"][0]["status"] == "purchased"


async def test_unknown_neighbourhood_is_404(client):
    assert (await client.get("/neighbourhoods/nope")).json()["error"]["code"] == "NEIGHBOURHOOD_NOT_FOUND"
    assert (await client.get(f"/neighbourhoods/{uuid.uuid4()}")).status_code == 404


# ------------------------------------------------------------------ admin management

async def test_admin_creates_neighbourhood_and_assigns_a_tour(client):
    admin = await make_admin(client)
    h = auth(admin["access_token"])
    hood = await client.post("/admin/neighbourhoods", json={"name": "Koramangala"}, headers=h)
    assert hood.status_code == 201 and hood.json()["slug"] == "koramangala"
    dup = await client.post("/admin/neighbourhoods", json={"name": "Koramangala"}, headers=h)
    assert dup.status_code == 409

    tour = await client.post(
        "/admin/tours",
        json={"name": "Koramangala Walk", "price_paise": 9900, "neighbourhood_id": hood.json()["id"],
              "is_featured": True, "includes": ["Audio guide"]},
        headers=h,
    )
    assert tour.status_code == 201, tour.text
    assert tour.json()["neighbourhood"]["slug"] == "koramangala" and tour.json()["includes"] == ["Audio guide"]

    bad = await client.post("/admin/tours", json={"name": "X", "neighbourhood_id": str(uuid.uuid4())}, headers=h)
    assert bad.status_code == 404 and bad.json()["error"]["code"] == "NEIGHBOURHOOD_NOT_FOUND"
    neg = await client.post("/admin/tours", json={"name": "X", "price_paise": -1}, headers=h)
    assert neg.status_code == 422
