# Business Rules — Purchase, Licensing & Anti-Sharing

> Implementation notes (kept in sync with code): device binding is stored as `purchases.device_id`
> (a client-generated identifier string) and login sessions live in `user_login_sessions`.
> The `bound_device_id` / `devices` / `auth_sessions` names below are the original design names.

## 1. Core rule: one purchase = one lifetime playback

- A `purchases` row with `status = 'completed'` grants exactly one right to walk that tour, ever.
- The tour is considered **consumed** the moment its `tour_sessions.completed = TRUE`.
- Once consumed, that user can never start a new session for that tour again — the app should show it as "Completed" with playback locked, not offer a replay button.
- If they want to experience it again, that requires a fresh purchase (re-buy), unless you later decide to offer a paid "replay" price point — not in scope now.

## 2. Interruption handling (recommended default)

**Recommendation: resuming an interrupted walk is NOT a new use.**

Reasoning: GPS/signal loss, app crashes, and dead batteries are environmental failures, not the user re-consuming the product. Penalizing that would feel unfair and generate support tickets/refund requests.

Rule:
- A `tour_sessions` row stays `completed = FALSE` until the user reaches the final stop (or explicitly taps "End Walk" after visiting all stops).
- While `completed = FALSE`, the session is resumable from `stops_visited` — same session_id, no new row created.
- Only marking `completed = TRUE` locks the tour. An abandoned/interrupted walk can sit in "in progress" indefinitely with no penalty.
- Edge case: if a user never returns to an in-progress walk, the tour stays usable — this is intentional. Only actual completion consumes the license.

## 3. Anti-account-sharing enforcement

Two independent mechanisms, both required:

### a) Device binding
- Each install gets a unique `device_identifier` (e.g. a persisted UUID generated on first app launch, not a hardware serial — avoids OS-level privacy restrictions).
- The **first time** a purchased tour is downloaded for offline use, the app records that device against the purchase (`purchases.bound_device_id`).
- Offline audio/route data for that tour will only decrypt/play on the bound device. If the same account logs in on a second device and tries to access that tour, it must re-download — which triggers rule (b) below.

### b) Single active session per account
- Logging in on a new device invalidates the previous device's session token immediately (server-side session table, not just local logout).
- Practical effect: if two people try to use one account on two phones, the second login kicks the first one out. This doesn't block a genuine device upgrade (user logs into their new phone, old one is simply logged out) but does block simultaneous shared use.
- A user switching devices legitimately will need to re-download any tours they want available offline on the new device — expected friction, not a bug.

### c) What this does NOT do
- It does not prevent someone from handing their *unlocked phone* to a friend for a single walk — that's outside what device+session binding can catch, and is treated as acceptable (same as sharing a Kindle unlocked on your own device).
- It does not require always-online DRM checks during the walk itself (the whole tour must work offline once downloaded) — enforcement happens at **download time** and **login time**, not continuously during playback.

## 4. Refunds / edge cases

- Refund eligibility: full refund allowed if `tour_sessions.stops_visited = 0` (i.e. never actually started) — this needs a business decision on a time window (e.g. within 14 days of purchase, standard practice).
- If a session is `completed = TRUE`, the purchase is non-refundable — the product was delivered.
- If GPS trigger failure causes a stop to be missed (a technical bug, not user behavior), support should be able to manually reset `stops_visited`/`completed` on a session via an admin action — this needs an admin tool, not user-facing.

## 5. What needs confirmation before engineering builds this

- Refund policy window (e.g. 14 days, or none) — legal/business decision, not engineering.
- Whether "Continue where you left off" persists across app reinstalls on the *same* device (recommend yes, tied to device_identifier, not just local app storage) — needs product sign-off.

## 6. Decisions recorded during implementation

- **Refund window:** 14 days from purchase, configurable via `REFUND_WINDOW_DAYS` (default 14).
- **Reschedule:** not supported. The "Reschedule" button in the bookings mock-up is dropped because a purchase is a one-time-use licence, not a time-slot booking.
- **OTP delivery:** email only for v1.
