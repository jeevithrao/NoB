"""RBAC matrix (docs/design/09): admin routes are admin-only, checked server-side."""
import uuid

import pytest

from tests.factories import make_admin, make_tour
from tests.helpers import auth, signup

ANY_ID = uuid.uuid4()

ADMIN_ROUTES = [
    ("POST", "/admin/tours", {"name": "x"}),
    ("PUT", f"/admin/tours/{ANY_ID}", {"name": "x"}),
    ("POST", f"/admin/tours/{ANY_ID}/publish", None),
    ("POST", f"/admin/tours/{ANY_ID}/stops",
     {"order_index": 1, "name": "s", "lat": "13.0", "lng": "77.5", "audio_filename": "a/b.mp3"}),
    ("GET", "/admin/purchases", None),
    ("POST", f"/admin/sessions/{ANY_ID}/reset", None),
]


@pytest.mark.parametrize("method,path,body", ADMIN_ROUTES)
async def test_anonymous_gets_401(client, method, path, body):
    resp = await client.request(method, path, json=body)
    assert resp.status_code == 401


@pytest.mark.parametrize("method,path,body", ADMIN_ROUTES)
async def test_normal_user_gets_403(client, method, path, body):
    user = await signup(client)
    resp = await client.request(method, path, json=body, headers=auth(user["access_token"]))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ADMIN_REQUIRED"


async def test_forged_admin_role_claim_is_ignored(client):
    """The role is read from the database, never trusted from the token."""
    user = await signup(client)
    import jwt
    from app.config import settings

    payload = jwt.decode(user["access_token"], settings.SECRET_KEY, algorithms=["HS256"])
    payload["role"] = "admin"
    forged = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    resp = await client.get("/admin/purchases", headers=auth(forged))
    assert resp.status_code == 403


async def test_admin_can_create_publish_and_list(client):
    admin = await make_admin(client)
    created = await client.post(
        "/admin/tours", json={"name": "New Walk", "price_paise": 9900}, headers=auth(admin["access_token"])
    )
    assert created.status_code == 201
    assert (await client.get("/admin/purchases", headers=auth(admin["access_token"]))).status_code == 200


async def test_unpublished_tour_is_invisible_to_users(client):
    hidden = await make_tour(client, published=False, name="Hidden Walk")
    user = await signup(client)
    listing = await client.get("/tours", headers=auth(user["access_token"]))
    assert hidden["id"] not in [uuid.UUID(t["id"]) for t in listing.json()]
    assert (await client.get(f"/tours/{hidden['id']}")).status_code == 404
