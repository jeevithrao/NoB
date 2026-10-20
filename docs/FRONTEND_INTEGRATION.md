# Frontend integration report — `nob-react-final.zip` vs backend at checkpoint 2

Reviewed: every line of `src/App.jsx` (1330), `data.js`, `images.js`, `styles.css` skimmed, README, package.json. Built it (`npm install && npm run build` succeeds, 385 kB JS).
Backend reviewed: tag `v0.2-cp2` (163 tests green).

---------------------------------------------------------------------------------------------------

## 1. Verdict

**The UI is good and the backend contract is close, but nothing is connected yet.** The app is a *clickable prototype*:

- It makes **zero API calls**. The only network requests are Wikipedia photo lookups and OpenStreetMap map tiles.
- All content (4 walks, 4 neighbourhoods, 12 passport slots, bookings, notifications, reviews) is hard-coded in `src/data.js`.
- Auth, payment, audio, GPS-triggering, notifications and settings are all simulated (`setTimeout`, fake QR, fixed 3:40 audio, "Demo: toggle GPS" buttons).
- There is no router, no API layer, no auth state, no env config. Screens switch with `useState('page')`.

So "connecting" = (a) a small amount of backend work so the API can express what the screens show, plus (b) a real amount of frontend work by your partner to replace every mock with a call. Rough split of the 16 screens:

| Bucket | Screens |
|---|---|
| No backend needed | Splash, About, Location prime |
| Connect almost as-is (rename fields, format money) | Login, Home, Explore (basic), Neighbourhood hub, My Bookings, Profile stats, Log out |
| Needs small backend additions first | Sign up (consents), Walk detail, Passport, Complete (rating/comment UI), Explore (filters), Profile (username/edit) |
| Needs new backend features | Notifications, Settings (preferences, export, delete), Forgot password |
| Needs the most frontend work, whatever the backend does | Active Walk (real audio + geofence + progress sync), Payment (Razorpay Checkout), OTP entry screen |

Roughly two-thirds of what the screens need already exists in the API; about a quarter needs small additions; the rest is new (notifications, account management).

---------------------------------------------------------------------------------------------------

## 2. Big things to know first

1. **It is a web app (React + Vite), not React Native.** The PRD/architecture assumed React Native with offline download and device binding. A browser app cannot reliably do the core walk experience with the phone locked in a pocket: iOS Safari stops `watchPosition` when the screen sleeps, and background audio is inconsistent. It works fine for demos, desktops, and a screen-on walk. Decide: ship as a web/PWA MVP (accept the limit), or treat this as the design reference and build the real client in React Native later. The backend is the same either way.
2. **Device binding assumes an app install.** Every auth call requires `device_identifier`. On web the client must invent one (UUID in localStorage). If the user clears site data or switches browser, their purchase looks bound to "another device" and they are locked out of what they paid for. We need a recovery path (decision D3).
3. **Offline-first is absent.** There is no "download" step, no service worker, no queued events. The backend supports it (package endpoint, batch events); the frontend doesn't use it.
4. **The prototype's content differs from the backend's seed data** (4 walks / 4 neighbourhoods named differently, MG Road doesn't exist in the DB, prices ₹249/199/free/229). The seed will be rewritten to match `data.js`.
5. **Several UI promises conflict with our business rules** (see section 5): "Valid until Dec 6" (our purchases don't expire), "Free cancellation 24h before" (we use a 14-day window), booking QR codes (nothing scans them), "Saved — HDFC Visa ····4821" (Razorpay owns payment methods), fake review counts and ratings (ours are computed from real data).

---------------------------------------------------------------------------------------------------

## 3. Screen by screen

Legend: ✅ backend ready · 🟡 small backend change · 🔴 new backend work · 🖥 frontend-only work

### Splash / About / Location prime
No backend. Location prime uses `navigator.geolocation`. 🖥 Keep as is. Remove "Replay intro".

### Sign up
UI: full name, email, password, confirm password (client-side only), required Terms/Privacy checkbox, optional marketing checkbox, Google button.
- ✅ `POST /auth/signup {email, password, full_name, device_identifier}` → `{access_token, refresh_token, user}`. Password min 8 matches the placeholder.
- 🟡 **Consent flags are not stored.** Add `accepted_terms: true` (required, 422 if false) and `marketing_opt_in`, plus `terms_accepted_at` / `terms_version` columns (DPDP/GDPR evidence).
- ✅ Google: Google Identity Services gives an `id_token` → `POST /auth/google`. Needs a Google client ID from you.
- 🖥 Show backend errors (`EMAIL_ALREADY_EXISTS` etc.); "Create account → Enable location" button then goes to location prime.

### Login
- ✅ `POST /auth/login`. 🖥 Store tokens; wrong-password error.
- 🔴 **Forgot password** is a dead link. Needs `POST /auth/forgot-password` + `POST /auth/reset-password` (email code), planned chunk 8.
- ✅ **Sign in with OTP** backend done, but 🖥 **there is no screen to type the code**. Needs a new screen (email → 6-digit code).
- 🖥 Remove the "Go to Explore" skip button, or turn it into "Browse as guest" (the catalogue endpoints are public; buying needs login).

### Home
- ✅ Featured carousel → `GET /tours/featured`. Neighbourhood strip → `GET /neighbourhoods`. "What walkers say" → `GET /reviews?limit=4`.
- 🔴 Bell + unread dot → needs notifications (below).
- 🖥 Empty states: at launch there are **no real reviews or ratings**; the carousel and the `★ 4.9` badge need a "New" / empty state. (The 4.9 / 128 reviews in the mock are fake.)

### Explore (search + filters)
UI filters: neighbourhood (multi), duration buckets (<60, 60–90, >90), price buckets (Free, <₹200, ₹200+), theme (Heritage, Culture, Nature, Colonial), free-text search.
- ✅ `q`, `free`, `min_price`, `max_price`, `sort`, `limit/offset` exist. `neighbourhood` accepts **one** slug/id.
- 🟡 Missing: multi-neighbourhood, `min_duration`/`max_duration`, `theme` (no such field on tours).
- Pragmatic option: with 5–10 walks at launch, **filter on the client** over `GET /tours` and skip server-side buckets. We add the `theme` field anyway so the data exists.

### Walk detail
| UI element | Backend today | Change |
|---|---|---|
| Title, neighbourhood, distance, duration | ✅ | `distance_km` arrives as a **string** ("2.30"): see change B6 |
| Rating "4.9 (128 reviews)" | ✅ `avg_rating`, `rating_count` | frontend must handle `null` |
| **Itinerary: stop cards (emoji, name, number)** | 🔴 stops are **only** returned by `/package` after purchase | add public `stops_preview` |
| Stop description line ("18th-century Shiva temple") | 🔴 no short description; `narrative_text` is the paid narration and must **not** be exposed pre-purchase | add `stops.blurb`, `stops.icon` |
| Meeting point ("Sampige Road Metro Gate") | 🔴 none | add `tours.start_point` |
| Language | ✅ `languages[]` | |
| Difficulty (Easy/Moderate) | 🔴 none | add `tours.difficulty` |
| Fitness & accessibility tags | 🔴 none | add `tours.tags[]` |
| Theme | 🔴 none | add `tours.theme` |
| Audio sample (title + 15 s player) | 🟡 `preview_audio_url` ✅ (no title) | add `preview_audio_title`; 🖥 replace the fake timer with `<audio>` |
| Photo gallery | ✅ `gallery_images[]` | 🖥 frontend currently loads Wikipedia photos by hard-coded slug; decision D6 |
| What's included | ✅ `includes[]` | copy must match refund rules |
| "About {neighbourhood}" text | 🟡 detail only has a `NeighbourhoodRef` (id, name, slug) | include `description` in the ref, or fetch `/neighbourhoods/{slug}` |
| Reviews for this walk | ✅ `GET /reviews?tour_id=` | |

### Booking sheet → payment → "You're in" → start
- 🖥 Today it fakes payment with a 1.8 s timer. With our API:
  1. `POST /purchases {tour_id}` → `{purchase_id, gateway_config}`.
  2. **Mock mode (current default):** purchase is already `completed`, `gateway_config={"mock":true}`: the sheet's "Pay" button can work *today* with no Razorpay account.
  3. **Real mode:** open Razorpay Checkout with `gateway_config`, then `POST /purchases/{id}/verify` with the 3 values Checkout returns.
- The UPI / Card / "Saved HDFC Visa" radio list is cosmetic: Razorpay Checkout has its own method picker. Remove the radio list or keep one "Pay" button. The "Saved card ····4821" row is fiction.
- 🟡 **Free walks (Cubbon Park).** Today `POST /purchases` **refuses** free tours; the session endpoint lets you walk a free tour with no purchase. So a free walk never appears in My Bookings, has no refund/stamp record. Decision D2.
- ✅ "Take me to the start" → start point = first stop's lat/lng; "Begin walk" → `POST /sessions {tour_id}` (resumes if one is in progress).

### My Bookings
- ✅ `GET /purchases?tab=upcoming|past` maps to "Ready to walk" / "Completed". Each row has tour, `walk_status`, `stops_visited`, `can_refund`, `refund_deadline`, `session_id`.
- ✅ "Start walk" → `POST /sessions`. "Cancel" → `POST /purchases/{id}/refund` (14-day window, not started). 🖥 Show Cancel only when `can_refund`.
- 🟡 Missing fields: `completed_at` ("Walked Mon, Aug 12"), `my_rating` / `reviewed` (drives "Leave review"), short human **booking ref** (frontend shows `B001`; ours are UUIDs).
- ⚠️ **"Valid until Dec 6, 2026" has no backend meaning.** A purchase is a lifetime, one-playback licence; nothing expires. Remove it (show "Purchased {date}" and the refund deadline) unless you want expiry (decision D4).
- ⚠️ The **QR code is fake** (derived from the id). Nothing in the product scans it. Remove it, or encode the booking ref if you want a "ticket" look.
- 🖥 "Leave review" button does nothing: needs the rating/comment UI (below).

### Passport
- ✅ `GET /me/passport` → stamps with `stamped`, `stamped_at`, tours totals.
- 🟡 UI shows **12 fixed slots** including neighbourhoods with no walks yet ("Not yet explored"). Ours lists only neighbourhoods that have a published walk (or a completion). Add the 12 neighbourhoods to the DB and let passport return empty ones (`include_empty`, default true).
- 🟡 Back of each stamp shows the **walk name** and date. Add `walk_name` to each stamp; add `emoji` to neighbourhoods.
- ✅ The "just earned" animation → `stamp_earned` from `GET /sessions/{id}/summary`.

### Neighbourhood hub
- ✅ `GET /neighbourhoods/{slug}` → description + its tours.
- 🟡 Tagline "Old Bangalore · 1 walk available": add `tagline` (text) or derive the count on the client. Add `emoji`.

### Notifications  🔴
UI: list grouped Today/Earlier, unread dot that fades, tap or swipe to dismiss, types `reminder | confirmed | new | review`. **No backend at all.**
- Add `notifications` table + `GET /me/notifications` (+ `unread_count`), `POST /me/notifications/{id}/read`, `POST /me/notifications/read-all`, `DELETE /me/notifications/{id}`.
- Auto-create: **confirmed** on purchase completed, **review** prompt when a walk completes, **new** when an admin publishes a tour (fan-out to users who opted in), **reminder** later (needs a scheduler, v1.1).
- No push notifications in this scope (no FCM/APNs). In-app list only. "Simulate new notification" button: remove.

### Active walk
Currently: Leaflet map with the route + numbered pins ✅ (coordinates = `stops[].lat/lng` from `/package`), user dot from `watchPosition` ✅, but:
- 🖥 **Audio is fake** (fixed 3:40 timer, speed/seek are UI only). Replace with `<audio src=audio_url>` from `/tours/{id}/package` (needs the `X-Device-Id` header and a prior `POST /purchases/{id}/bind-device`).
- 🖥 **No geofence.** Stops advance via the "Next stop" button. The product's core promise (auto-play on entering `trigger_radius_m`) is not built. Needs a distance check against each stop with debounce.
- 🖥 **Progress isn't saved.** On arrival/audio start/finish send `POST /sessions/{id}/events/batch` (backend dedupes by `client_event_id`); on reopen `POST /sessions` resumes with `stops_visited`.
- "Finish walk" / "End walk early" → `POST /sessions/{id}/complete` (backend allows early finish, by design).
- 🖥 Remove "Demo: toggle GPS lost banner". Start at stop 1 (currently starts at 2).

### Walk complete
- ✅ `GET /sessions/{id}/summary` gives stops, distance, duration, avg rating, `stamp_earned`, `liked`, `commented`, `my_rating`.
- ✅ Like → `POST/DELETE /tours/{id}/like`.
- 🖥 **"Comment" button does nothing and there is no star-rating control.** Needs a small UI: 1–5 stars → `PUT /tours/{id}/rating`; comment box (max 1000 chars) → `POST /tours/{id}/comments`.
- Note: `duration_min` in the summary is the walk's nominal length, not actual time walked (actual = `completed_at - started_at`; easy to add).

### Profile
- ✅ Stats → `GET /me/stats` returns `walks_completed, distance_km, stops_visited, listening_minutes, neighbourhoods_stamped`.
- 🟡 UI shows **Walks / km / Reviews**: `reviews_count` missing → add.
- 🔴 The form (full name / username / email) is blank and not wired. Need `GET /auth/me` to prefill and `PATCH /me {full_name, username}`. **`username` doesn't exist** in the User model (add unique, optional). Recommend **email read-only** (changing it needs re-verification).
- Avatar is the initial letter only: nothing to upload. Fine for v1.
- "My Passport · 3 of 12" ✅ from passport.

### Settings
| Row | Backend |
|---|---|
| GPS tracking toggle | none (device permission, client only) |
| Notifications toggle | 🔴 `PATCH /me/preferences {notifications_enabled}` |
| Analytics sharing (opt-in) | 🔴 `PATCH /me/preferences {analytics_opt_in}` |
| Download my data | 🔴 `GET /me/export` (JSON: profile, purchases, sessions, ratings, comments, likes, saved) |
| Delete my account | 🔴 `DELETE /me`. **Must anonymise, not hard-delete**: payment/purchase rows must be retained for accounting; remove PII, revoke sessions |
| Terms / Privacy / Refund policy / About | static pages: you need real text and URLs (frontend rows are not links yet) |
| Data grievance officer `grievance@nob.app` | needs a real mailbox |
| Photo credits | Wikipedia (frontend only) |
| Log out | ✅ `POST /auth/logout` |

---------------------------------------------------------------------------------------------------

## 4. Backend changes (what changes in what we already built)

### A. Contract additions (additive migrations; nothing existing breaks)
| # | Change | Touches |
|---|---|---|
| A1 | `tours`: add `theme`, `difficulty`, `start_point`, `tags[]`, `preview_audio_title` → in list/detail/admin create/update | migration 0006, `Tour` model, `TourListItem/Detail`, admin schemas |
| A2 | `stops`: add `blurb`, `icon` | migration, `Stop` model, `StopCreate`, `StopOut` |
| A3 | `TourDetail.stops_preview[]` = `{order_index, name, blurb, icon}` (**never** narration/audio/coords) | `tours.py` detail |
| A4 | `neighbourhoods`: add `tagline`, `emoji`; `NeighbourhoodRef` gains `description`, `emoji` | model, schemas, admin |
| A5 | `BookingOut`: add `completed_at`, `my_rating`, `booking_ref`, `tour.theme` | `purchases.py`, schema, `purchases.booking_ref` column |
| A6 | Passport: `include_empty` (default true), stamp gets `walk_name`, `emoji` | `me.py` |
| A7 | Stats: add `reviews_count` | `me.py` |
| A8 | Signup: `accepted_terms` (required) + `marketing_opt_in`; store `terms_accepted_at`, `terms_version` | `auth.py`, `User` |
| A9 | Seed rewritten to mirror the frontend content (4 neighbourhoods + 8 more passport slots, 4 walks, prices 24900/19900/0/22900, stops with blurb/icon/coords) | `seed_data.py`, placeholder audio generator |

### B. Behaviour changes to existing code
| # | Change | Why |
|---|---|---|
| B1 | **Free walks**: `POST /purchases` on a free tour creates a completed ₹0 "claim" (no gateway), so it shows in Bookings and can be walked | otherwise free walks don't appear in My Bookings (D2) |
| B2 | **422 validation errors normalised** to `{"error":{"code":"VALIDATION_ERROR","message", "fields":{...}}}` | today only `HTTPException` uses our envelope; Pydantic errors still return FastAPI's `{"detail":[...]}`, so the frontend would need two error parsers |
| B3 | Explore: optional `min_duration`, `max_duration`, `theme`, repeatable `neighbourhood` | filters in UI (or do it client-side) |
| B4 | `GET /tours/{id}` includes neighbourhood `description` | "About {neighbourhood}" |
| B5 | Session summary: add actual walked minutes | "Duration" stat |
| B6 | Return `distance_km` and stop `lat/lng` as **numbers** (not Decimal strings) | JSON currently carries `"2.30"`; JS needs `Number()` everywhere |
| B7 | CORS: add the real frontend origin(s). Dev origin `http://localhost:5173` (Vite) is already allowed | config |
| B8 | Walk start: optionally require the device header and check the binding (closes the gap I flagged earlier) | licence integrity |

### C. New features
| # | Feature | Endpoints |
|---|---|---|
| C1 | Notifications | `GET /me/notifications`, read, read-all, delete; auto-created on purchase/complete/publish |
| C2 | Account | `PATCH /me` (full_name, username), `PATCH /me/preferences`, `GET /me/export`, `DELETE /me` |
| C3 | Password reset | `POST /auth/forgot-password`, `POST /auth/reset-password` |
| C4 | Web device recovery (if web is shipped) | e.g. `POST /purchases/{id}/rebind-device`, once per 30 days after re-auth (D3) |

### D. Existing tests
All 163 pass today. Expect: A/B changes will edit a handful of existing assertions (field additions don't break them; B1, B2 and B6 change a few) and add ~40–60 new tests.

---------------------------------------------------------------------------------------------------

## 5. Rules in the UI that conflict with the backend (pick one side)

| UI says | Backend rule | Recommendation |
|---|---|---|
| "Valid until Dec 6, 2026" | no expiry; lifetime licence | remove the text |
| "Free cancellation 24h before" (included list, walk 1) | refund within **14 days if walk not started** | use the backend `includes[]` text; align copy |
| Cancel → "refund within 5–7 business days" | gateway-dependent | fine, soften wording |
| `★ 4.9 (128 reviews)` | computed from real ratings | show "New" until ≥1 rating |
| "Tour locked · purchased once" | ✅ matches | keep |
| Booking QR code | not used anywhere | remove or encode booking ref |
| "Saved — HDFC Visa" | Razorpay owns this | remove |
| 12-neighbourhood passport incl. empty ones | list only neighbourhoods with walks | add empty ones to the DB |
| Neighbourhood "1 walk available" | dynamic | derive from the list length |

---------------------------------------------------------------------------------------------------

## 6. Decisions (RESOLVED 2026-10-20)

All recommended options were accepted: D1 web/PWA MVP now; D2 free walks are a 0-paise claim; D3 one self-service re-bind per 30 days; D4 purchases never expire; D5 in-app notifications only; D6 images: local/free for now, owned photos later (frontend keeps its own image source until `cover_image`/`gallery_images` are filled); D7 legal text still to be written (see below); D8 mock payments until Razorpay keys exist. Cancellation copy/rules are left as is. The fake booking QR and demo buttons stay in the prototype on purpose.

Original questions:

- **D1. Web vs React Native.** Ship this as a web/PWA MVP (accept the locked-screen limitation), or use it as the design reference for a later RN app? *(No backend impact, big product impact.)*
- **D2. Free walks:** create a ₹0 claim (recommended: appears in bookings, one-time like paid ones) or keep them purchase-less?
- **D3. Web device recovery:** if someone clears their browser storage, how do they regain a purchase? Recommend: one self-service re-bind per 30 days after login. Alternative: support-only (admin reset).
- **D4. Expiry:** confirm purchases never expire (recommended), or tell me the validity period.
- **D5. Notifications v1:** in-app list only (recommended), or also email?
- **D6. Images:** Wikipedia hot-linking in a paid product is a licensing/attribution risk and is slow. Recommend: you store licensed or owned photos and we serve them via `cover_image` / `gallery_images`.
- **D7. Legal pages & grievance email:** you provide text + a real mailbox before launch.
- **D8. Razorpay:** keep mock until you have keys; the integration path is ready.

---------------------------------------------------------------------------------------------------

## 7. Frontend checklist (for your partner)

1. Add an API layer (`src/api.js`) with base URL from `VITE_API_URL`, bearer token, auto-refresh on 401, one error parser for `{error:{code,message}}`.
2. Replace `useState` navigation with a router (needed for deep links, back button, payment return).
3. Generate and persist a `device_identifier` (UUID in localStorage) and send it on signup/login/refresh/package.
4. Replace every import of `data.js` with fetches; format `price_paise` → ₹; `distance_km`/`duration_min` → "2.3 km · 90 min".
5. Add screens: OTP entry, forgot/reset password, rating + comment UI on Complete, empty states (no reviews, no ratings, no bookings).
6. Real audio element, geofence trigger, event batching + resume, signed-URL expiry handling (`signed_url_expires_in`).
7. Razorpay Checkout integration (script from `checkout.razorpay.com`) + `/verify`.
8. Remove prototype scaffolding: nav row, "Go to Explore", "Replay intro", "Demo: GPS lost", "Simulate notification", fake QR, fake card.
9. Handle the "logged in on another device" 401 with a clear message.
10. Do **not** call Wikipedia in production (D6).

---------------------------------------------------------------------------------------------------

## 8. Revised plan (replaces chunks 8–11)

| # | Chunk | Content |
|---|---|---|
| 8 | `feat/contract-alignment` | A1–A9, B2–B6, B7 + tests; seed mirrors frontend |
| 9 | `feat/free-claims-and-device` | B1, B8, C4 (after D2/D3) |
| 10 | `feat/account` | C2, C3, signup consents |
| 11 | `feat/notifications` | C1 |
| 12 | `chore/integration` | OpenAPI export, Postman collection, `docker-compose` (db + api), Vite proxy/CORS, a reference `api.js` for the partner, end-to-end smoke script (signup → buy → walk → complete → stamp) |
| 13 | `chore/deploy` + `docs/final-sync` | staging config, README/docs |

Estimate: backend chunks 8–12 are roughly 1.5–2 working days. Frontend wiring is the long pole (roughly 3–4 days for one developer, most of it the Active Walk and payment).

---------------------------------------------------------------------------------------------------

## 9. Field mapping (frontend → API)

| Frontend (`data.js`) | API |
|---|---|
| `walk.id` (number) | `tour.id` (UUID string) |
| `t` | `name` |
| `tag` / `neighbourhood` (slug) | `neighbourhood.name` / `neighbourhood.slug` |
| `price: '₹249'` / `'Free'` | `price_paise: 24900` / `is_free` |
| `meta: '2.3km · 90 min'`, `distance`, `duration` | `distance_km`, `duration_min` |
| `rating: '4.9'`, `stars`, `reviewCount` | `avg_rating`, `rating_count` (nullable) |
| `desc` | `description` |
| `start` | `start_point` (new) |
| `theme`, `difficulty`, `tags`, `sample.title` | new fields A1 |
| `language: 'English · Kannada'` | `languages[]` |
| `included[]` | `includes[]` |
| `stops[].n / d / e / coords` | `stops_preview[].name / blurb / icon`; coords from `/package` |
| `bg`, `icon` (colour/emoji tiles) | `cover_image` fallback; `emoji` (new) |
| `bookings.upcoming[].validUntil` | none (removed) |
| `bookings.past[].walkedOn / reviewed` | `completed_at` / `my_rating` (new) |
| `passportSlots[].collected / walkName / date` | `stamped` / `walk_name` (new) / `stamped_at` |
| `reviews[].stars (string)` | `rating` (int) |
| `notificationsData` | `/me/notifications` (new) |
