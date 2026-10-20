import re
import uuid

from app.services import email as email_service


def new_email(prefix: str = "walker") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}@nobtests.com"


def new_device() -> str:
    return f"device-{uuid.uuid4().hex[:12]}"


async def signup(client, email: str | None = None, password: str = "correct-horse-1", device: str | None = None):
    email = email or new_email()
    device = device or new_device()
    resp = await client.post(
        "/auth/signup",
        json={"email": email, "password": password, "full_name": "Test Walker", "device_identifier": device, "accepted_terms": True},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return {"email": email, "password": password, "device": device, **body}


async def login(client, email: str, password: str, device: str):
    return await client.post(
        "/auth/login", json={"email": email, "password": password, "device_identifier": device}
    )


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def last_otp_code() -> str:
    """The 6-digit code from the newest email in the memory outbox."""
    outbox = email_service.get_email_backend().outbox
    assert outbox, "no email was sent"
    match = re.search(r"\b(\d{6})\b", outbox[-1].body)
    assert match, outbox[-1].body
    return match.group(1)


async def buy(client, token: str, tour_id):
    resp = await client.post("/purchases", json={"tour_id": str(tour_id)}, headers=auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def start_walk(client, token: str, tour_id):
    resp = await client.post("/sessions", json={"tour_id": str(tour_id)}, headers=auth(token))
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


async def arrive(client, token: str, session_id, stop_ids):
    from datetime import datetime, timezone

    events = [
        {
            "client_event_id": str(uuid.uuid4()),
            "stop_id": str(stop_id),
            "event_type": "arrived",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        for stop_id in stop_ids
    ]
    resp = await client.post(f"/sessions/{session_id}/events/batch", json={"events": events}, headers=auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


async def complete_walk(client, token: str, session_id):
    resp = await client.post(f"/sessions/{session_id}/complete", headers=auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()
