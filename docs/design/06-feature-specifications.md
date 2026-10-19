# Feature Specifications — v1

---

## Feature 1: Purchase & Licensing

**Trigger:** User taps "Purchase" on Tour Detail.

**Flow:**
1. Client calls `POST /purchases` with `tour_id`. Server checks: tour exists, is published, user doesn't already have a `completed` purchase for it (block duplicate purchase of an already-owned tour).
2. Server creates a `purchases` row (`status = 'pending'`), creates an order with the payment gateway, returns `gateway_order_id` + client config to the app.
3. App opens gateway checkout UI (Razorpay/Stripe SDK).
4. On payment success, gateway sends a webhook to `POST /webhooks/payment`. Server verifies signature, sets `purchases.status = 'completed'`, records `gateway_payment_id` and `amount_paise`.
5. App polls or listens for purchase confirmation, then transitions to Download/Offline Prep.

**Failure handling:**
- Payment fails/cancelled → `purchases.status = 'failed'`. App shows Error state, allows retry (creates a new pending purchase attempt — don't reuse a failed row's gateway IDs).
- Webhook never arrives (network issue on gateway side) → app should have a manual "Check payment status" fallback that calls `GET /purchases/{id}` to re-check, since offline-first UX can't rely purely on push confirmation.

**Licensing enforcement (ties to Business Rules doc):**
- A purchase alone does not equal unlimited access — it grants exactly one playback, consumed when `tour_sessions.completed = TRUE`.
- Once consumed, `GET /tours/{id}` for that user should return a `status: "completed_locked"` flag so the client can render the locked state, and must reject any attempt to `POST /sessions` (start a new walk) for that tour+user.

---

## Feature 2: GPS-Triggered Audio Playback

**Trigger:** User taps "Start Walk" on the Route-to-Start screen, having arrived at (or near) the tour's first stop.

**Behavior:**
1. Client creates or resumes a `tour_sessions` row (`POST /sessions` or resume existing non-completed one).
2. Client loads the downloaded stop list (ordered by `order_index`) with lat/lng and `trigger_radius_m` for each — this all runs from local storage, no network required.
3. Device location is polled continuously (recommend: foreground GPS updates every 3–5 seconds, adjustable for battery).
4. When the user's current position is within `trigger_radius_m` of the **next un-visited stop** (in order — stops cannot be skipped ahead by walking past them out of order... see note below), the app:
   - Plays that stop's audio file from local storage.
   - Logs a `session_events` row (`event_type = 'arrived'`, then `'audio_started'`, then `'audio_finished'`) — queued locally if offline, synced when back online.
   - Increments `tour_sessions.stops_visited`.
5. On reaching the final stop and its audio finishing, prompt "End Walk?" → sets `completed = TRUE`, `completed_at = NOW()`.

**Edge cases needing explicit decisions:**
- **Out-of-order arrival** (user's route naturally passes stop 3 before stop 2): recommend allowing out-of-order triggering rather than blocking it — feels more natural on a real walk. `order_index` still determines the *narrative* order shown in the UI/summary, not a hard gate on playback.
- **Overlapping trigger radii** (two stops close together): only trigger the nearest un-visited one; don't double-fire.
- **GPS drift/inaccuracy in dense urban areas:** recommend a minimum radius floor (e.g. 20m) even if content creators set a smaller one, to avoid false triggers from GPS jitter.

---

## Feature 3: Offline Download & Sync

**Trigger:** Immediately after a successful purchase (or manually from a "Download" button on an owned tour).

**Flow:**
1. Client calls `GET /tours/{id}/package` (requires valid purchase). Server returns a manifest: stop list (lat/lng, order, trigger radius, narrative text) + signed URLs for each audio file.
2. Client downloads all audio files to local storage, shows progress (percentage or MB downloaded).
3. On first successful full download, client calls `POST /purchases/{id}/bind-device` with its `device_identifier`. Server sets `purchases.bound_device_id`.
4. All subsequent playback for that tour checks against local cached data — **no network calls required during the actual walk.**

**Sync behavior for session events (offline-first):**
- `session_events` and `tour_sessions` progress are written locally first, queued, and synced to the server opportunistically (app foreground, network available) via `POST /sessions/{id}/events/batch`.
- Server treats incoming events as append-only and idempotent (dedupe by client-generated event UUID) to handle retried syncs safely.

**Device binding conflict:**
- If a user tries to download a tour already bound to a different device on their account, server returns a `409` with a clear reason — client should prompt "This tour was downloaded on another device. Re-download here? Your other device will need to sign in again to use it."

---

## Feature 4: Route Navigation to Tour Start

**Trigger:** After download completes (or when opening an in-progress tour from Home Feed/Profile).

**Flow:**
1. Client requests current location (device GPS/location services permission required — must be requested with clear rationale copy, not silently).
2. Client calls the maps SDK (Mapbox/Google Maps) to draw a route from current location to the tour's first stop coordinates (walking directions).
3. Screen shows: distance/ETA to start, a "Start Walk" button that becomes active once the user is within a reasonable proximity of the start point (recommend: same trigger radius logic as stop 1, or a looser fixed threshold like 100m — needs a product call).
4. If user is very far from the tour's city/area (e.g. testing from home), still allow "Start Walk" manually rather than hard-blocking — but show a warning ("You're far from the tour start — audio will begin once you're within range").

**Note:** This screen requires third-party maps SDK integration and location permissions — flag early with the mobile dev team since App Store/Play Store review requires clear permission-usage descriptions for background/foreground location.
