# Product Requirements Document (PRD)
## Neighbourhoods of Bangalore — v1

---

## 1. Overview

**Product:** A mobile app (React Native) that sells self-guided, GPS-triggered audio walking tours of Bangalore neighbourhoods. A user purchases a tour, downloads it for offline use, walks to the start point, and audio narration fires automatically as they reach each stop along a ~1–3km route.

**Reference docs:** Vision & Problem Statement, MVP Scope, Business Rules & Licensing (see prior docs). This PRD is the single source of truth for what gets built in v1 — if something conflicts with an earlier doc, this one wins.

---

## 2. Goals for v1

- Launch with a small number (aim: 5–10) of fully produced, high-quality Bangalore neighbourhood tours.
- Prove the core mechanic works reliably: GPS-triggered audio playback, offline, at walking pace, without babysitting from the user.
- Prove people will pay a one-time fee per tour.
- Keep the account model simple but airtight against sharing (single device + single session).

**Non-goals for v1:** multi-city, subscriptions, social feed/DMs, user-generated tours, ads, business listings. (Full list in Out-of-Scope doc.)

---

## 3. Users & Roles

| Role | Description |
|---|---|
| **User (Wanderer)** | Browses tours, purchases, downloads, walks, leaves likes/comments. |
| **Admin** | Publishes/unpublishes tours, uploads stop audio + GPS data, views purchases, can manually reset a stuck session (support tooling). |

(Full permission breakdown belongs in the RBAC/Permission Matrix doc — referenced, not duplicated here.)

---

## 4. Core User Flow (high level)

1. **Discover** — Browse tours via Home Feed (list) or Map screen (stylised illustrated map with pins for available walks near the user).
2. **Decide** — Open a tour detail page: description, distance, duration, price, preview.
3. **Purchase** — Pay via gateway (Razorpay/Stripe-style). Purchase unlocks that tour permanently for playback (subject to the one-lifetime-use rule).
4. **Prepare** — Download the tour (audio files + stop/route data) for offline use. Download binds the purchase to this device.
5. **Navigate** — App shows the route from current location to the tour's starting point.
6. **Walk** — User starts the walk. GPS tracks position; audio auto-fires when the user enters a stop's trigger radius, in order. Progress (`stops_visited`) is tracked live, works fully offline.
7. **Complete** — On reaching the final stop (or explicit "End Walk"), the session is marked `completed`. This is the point where the license is consumed — no replay without repurchase.
8. **React** — User can like/comment on the tour after completion.

---

## 5. Feature List (v1)

| # | Feature | Priority |
|---|---|---|
| 1 | Auth: sign up/sign in (email + Google), single active session enforcement | Must |
| 2 | Device registration & binding (first-launch device ID) | Must |
| 3 | Home feed — list of neighbourhood tours | Must |
| 4 | Map screen — illustrated map, pins for tours near user | Must |
| 5 | Tour detail page | Must |
| 6 | Purchase flow (payment gateway integration) | Must |
| 7 | Offline download (audio + route/stop data), bound to device | Must |
| 8 | Route navigation to tour start point | Must |
| 9 | Live GPS-triggered audio playback during walk | Must |
| 10 | Session tracking (in-progress / completed, resumable) | Must |
| 11 | Saved/bookmarked tours (wishlist) | Should |
| 12 | Likes on completed tours | Should |
| 13 | Comments on completed tours | Should |
| 14 | Profile screen (basic info) | Must |
| 15 | Settings screen (About, Privacy, Help) | Should |
| 16 | Admin: tour/stop upload & publish | Must (internal tool, can be minimal UI) |
| 17 | Admin: view purchases, manually reset a session | Must (internal tool) |

Detailed behavior for #1, #2, #6, #7, #8, #9 belongs in the separate Feature Specification doc (next deliverable) — this list is scope, not implementation detail.

---

## 6. Key Business Rules (summary — full detail in Business Rules doc)

- One purchase = one lifetime playback. Tour locks after `tour_sessions.completed = TRUE`.
- Interrupted walks are resumable and do NOT consume the license — only full completion does.
- Purchase is bound to the device that first downloads it; a second device requires re-download, which is gated by single-session login (logging in elsewhere kicks out the old session).
- Refund policy: full refund only if the walk was never started (`stops_visited = 0`); policy window (e.g. 14 days) needs a business decision.

---

## 7. Screens (v1 — matches existing Lovable mockups)

Splash → Map → Home Feed → Tour Detail → Purchase → Download/Offline prep → Route-to-start → Active Walk → Walk Complete → Profile → Settings → Sign Up / Sign In / OTP / Welcome (auth flow, already designed).

Full screen-to-screen transition logic goes in the User Flow/Sitemap doc (next deliverable).

---

## 8. Success Criteria for v1 launch

- A user can complete a full tour end-to-end fully offline, with all stop audio firing within their configured trigger radius, with no manual intervention.
- Purchase → download → walk → complete happens without app crashes across at least iOS + Android reference devices.
- Account-sharing prevention (device bind + single session) verified: a second device cannot use a tour purchased and downloaded by a different device without a fresh login that invalidates the first.
- At least 5 tours fully produced and published at launch.

---

## 9. Open Questions (need business/product decisions, not engineering)

- Refund policy time window.
- Whether "Business Plans" (seen in Settings/About mockups) is built at all in v1, or fully hidden until the monetization model for it is decided. **Recommendation: hide this entry entirely in v1** rather than build a half-defined feature — revisit post-launch.
- Pricing per tour (flat rate vs. varies by tour length/production cost) — needed before the purchase flow spec can be finalized.

---

## 10. Tech Stack (confirmed)

- **Frontend:** React Native (iOS + Android)
- **Backend:** Python (FastAPI recommended)
- **Database:** PostgreSQL (schema + extensions already drafted)
- **Storage:** Object storage for audio files and images (S3-compatible)
- **Maps/Geolocation:** Mapbox or Google Maps SDK + on-device location services
- **Payments:** Razorpay/Stripe-style gateway (schema already assumes this)

Full rationale belongs in the Tech Stack Decision doc / System Architecture doc (later deliverable).
