"""End-to-end smoke test against a RUNNING API (dev, mock payments).

    python scripts/smoke_e2e.py [http://localhost:8000]

Walks one brand-new user through: sign up -> browse -> buy -> bind device -> download
package -> walk every stop -> complete -> summary/stamp -> rate/like/comment -> bookings
-> passport/stats. Exits non-zero on the first failed step.
"""
import sys
import uuid
from datetime import datetime, timezone

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"


def step(name: str, resp: httpx.Response, expect: int | tuple[int, ...] = 200):
    ok = resp.status_code in ((expect,) if isinstance(expect, int) else expect)
    print(f"{'OK  ' if ok else 'FAIL'} {name} -> {resp.status_code}")
    if not ok:
        print(resp.text)
        sys.exit(1)
    return resp.json() if resp.content and "json" in resp.headers.get("content-type", "") else None


def main() -> None:
    http = httpx.Client(base_url=BASE, timeout=20)
    device = f"smoke-{uuid.uuid4().hex[:10]}"
    email = f"smoke_{uuid.uuid4().hex[:8]}@example.com"

    auth = step("signup", http.post("/auth/signup", json={
        "email": email, "password": "correct-horse-1", "full_name": "Smoke Tester",
        "device_identifier": device, "accepted_terms": True, "marketing_opt_in": False}), 201)
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    step("me", http.get("/auth/me", headers=headers))

    tours = step("list tours", http.get("/tours"))
    paid = next(t for t in tours if not t["is_free"])
    free = next(t for t in tours if t["is_free"])
    step("featured", http.get("/tours/featured"))
    step("neighbourhoods", http.get("/neighbourhoods"))
    detail = step("tour detail", http.get(f"/tours/{paid['id']}"))
    assert detail["stops_preview"] and "narrative_text" not in detail["stops_preview"][0]

    purchase = step("buy (mock)", http.post("/purchases", json={"tour_id": paid["id"]}, headers=headers), 201)
    assert purchase["status"] == "completed", purchase
    step("bind device", http.post(f"/purchases/{purchase['purchase_id']}/bind-device",
                                  json={"device_identifier": device}, headers=headers))
    pkg = step("package", http.get(f"/tours/{paid['id']}/package", headers={**headers, "X-Device-Id": device}))
    audio = http.get(pkg["stops"][0]["audio_url"] if pkg["stops"][0]["audio_url"].startswith("http")
                     else BASE + pkg["stops"][0]["audio_url"])
    step("download first audio file", audio)

    session = step("start walk", http.post("/sessions", json={"tour_id": paid["id"]}, headers=headers), 201)
    events = [{"client_event_id": str(uuid.uuid4()), "stop_id": s["id"], "event_type": "arrived",
               "occurred_at": datetime.now(timezone.utc).isoformat()} for s in pkg["stops"]]
    step("arrive at every stop", http.post(f"/sessions/{session['id']}/events/batch",
                                           json={"events": events}, headers=headers))
    step("complete walk", http.post(f"/sessions/{session['id']}/complete", headers=headers))
    summary = step("walk summary", http.get(f"/sessions/{session['id']}/summary", headers=headers))
    print(f"     stamp earned: {summary['stamp_earned']}")

    step("rate", http.put(f"/tours/{paid['id']}/rating", json={"rating": 5}, headers=headers))
    step("like", http.post(f"/tours/{paid['id']}/like", headers=headers))
    step("comment", http.post(f"/tours/{paid['id']}/comments", json={"comment_text": "Smoke test walk."},
                              headers=headers), 201)
    step("reviews feed", http.get("/reviews"))

    step("claim free walk", http.post("/purchases", json={"tour_id": free["id"]}, headers=headers), 201)
    bookings = step("bookings", http.get("/purchases", headers=headers))
    print(f"     bookings: {[b['booking_ref'] + ' ' + b['walk_status'] for b in bookings]}")
    passport = step("passport", http.get("/me/passport", headers=headers))
    print(f"     stamps: {passport['stamps_collected']}/{passport['total_neighbourhoods']}")
    stats = step("stats", http.get("/me/stats", headers=headers))
    print(f"     stats: {stats}")
    step("logout", http.post("/auth/logout", headers=headers), 204)
    print("\nALL STEPS PASSED")


if __name__ == "__main__":
    main()
