"""
Phase 1 end-to-end verification script.
Tests the full purchase → walk flow using the real database.
Run with: venv\Scripts\python.exe test_phase1.py
"""
import json
import urllib.request
import urllib.error
import uuid
from datetime import datetime, timezone

BASE = "http://127.0.0.1:8000"
HEADERS = {"Content-Type": "application/json"}


def call(method, path, body=None, token=None):
    headers = dict(HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def ok(label, status, expected=None):
    symbol = "✅" if (expected is None and status < 400) or status == expected else "❌"
    print(f"  {symbol} [{status}] {label}")
    return symbol == "✅"


print("\n=== Phase 1 — End-to-end API verification ===\n")

# 1. Signup
device_id = "test-device-phase1"
test_email = f"walker_{uuid.uuid4().hex[:6]}@nob.test"
status, body = call("POST", "/auth/signup", {
    "email": test_email,
    "password": "testpass123",
    "full_name": "Test Walker",
    "device_identifier": device_id
})
ok("POST /auth/signup → 201", status, 201)
token = body.get("access_token", "")
if not token:
    print("  ❌ No access_token in response — stopping.", body)
    exit(1)
print(f"     email: {test_email}")

# 2. Browse tours
status, body = call("GET", "/tours?city=Bangalore", token=token)
ok(f"GET /tours?city=Bangalore → 3 tours (got {len(body)})", status)
if len(body) < 3:
    print("  ❌ Expected 3 tours — stopping.", body)
    exit(1)

# Find the first paid tour (Malleshwaram)
paid_tour = next((t for t in body if not t["is_free"]), None)
free_tour = next((t for t in body if t["is_free"]), None)
print(f"     Paid tour: {paid_tour['name']}")
print(f"     Free tour: {free_tour['name']}")

# 3. Purchase paid tour
status, body = call("POST", "/purchases", {"tour_id": paid_tour["id"]}, token=token)
ok("POST /purchases → 201", status, 201)
purchase_id = body.get("purchase_id")
print(f"     purchase_id: {purchase_id}")
print(f"     status: {body.get('status')} (should be 'completed' with MOCK_PAYMENTS)")

# 4. Bind device
status, body = call("POST", f"/purchases/{purchase_id}/bind-device",
                    {"device_identifier": device_id}, token=token)
ok("POST /purchases/{id}/bind-device → 200", status, 200)

# 5. Download tour package (paid)
status, body = call("GET", f"/tours/{paid_tour['id']}/package", token=token)
ok(f"GET /tours/{{id}}/package → {len(body.get('stops', []))} stops", status)
stops = body.get("stops", [])
print(f"     audio_url[0]: {stops[0]['audio_url'] if stops else 'none'}")

# 6. Start a session
status, body = call("POST", "/sessions", {"tour_id": paid_tour["id"]}, token=token)
ok("POST /sessions → 201", status, 201)
session_id = body.get("session_id") or body.get("id")
print(f"     session_id: {session_id}")

# 7. Submit a stop event (batch)
first_stop_id = stops[0]["id"] if stops else None
status, body = call("POST", f"/sessions/{session_id}/events/batch", {
    "events": [{
        "client_event_id": str(uuid.uuid4()),
        "stop_id": first_stop_id,
        "event_type": "arrived",
        "occurred_at": datetime.now(timezone.utc).isoformat()
    }]
}, token=token)
ok("POST /sessions/{id}/events/batch → 2xx", status)

# 8. Complete session
status, body = call("POST", f"/sessions/{session_id}/complete", token=token)
ok("POST /sessions/{id}/complete → 2xx", status)

# 9. Free tour — package should work without purchase
status, body = call("GET", f"/tours/{free_tour['id']}/package", token=token)
ok(f"GET free tour package → {len(body.get('stops', []))} stops (no purchase needed)", status)

# 10. Duplicate purchase should return 409
status, body = call("POST", "/purchases", {"tour_id": paid_tour["id"]}, token=token)
ok("POST /purchases (duplicate) → 409 TOUR_ALREADY_OWNED", status, 409)

print("\n=== Done ===\n")
print("Open http://127.0.0.1:8000/docs to explore manually with Swagger.")
print(f"Admin login: admin@nob.app / AdminPass123!")
print(f"Test user:   {test_email} / testpass123")
