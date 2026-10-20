# API changelog

Changes relative to `design/07-api-specification.md`. Newest first. Fold into the spec at the end of each checkpoint.

## Already in code before the 3-day plan
- `POST /auth/request-otp`, `POST /auth/verify-otp`, `POST /auth/refresh`, `GET /auth/me`
- `POST /purchases/{id}/refund`
- `DELETE /tours/{id}/comments/{comment_id}`
- `GET /saved-tours`
- `POST /admin/audio/upload`
- `GET /media/...` (HMAC-signed audio serving)
- Auth responses return `{access_token, refresh_token, user}` (refresh token rotation not yet implemented).

## Unreleased
### Auth (fix/otp-takeover)
- **Changed** `POST /auth/request-otp`: the code is now emailed and is **not** in the response. The response is the same whether or not the account exists. Max 3 codes per email per 10 min (`429 OTP_REQUEST_LIMIT`); a new code invalidates the previous one. In development only, `EXPOSE_DEV_OTP=true` adds `_dev_otp`.
- **Changed** `POST /auth/verify-otp`: unchanged contract; codes are stored as keyed HMACs.
- **New error** `429 RATE_LIMITED` (with `Retry-After`) on signup, login, google, request-otp, verify-otp (10/min per IP and per account by default).
- **Changed** Google sign-in no longer returns verifier internals in `INVALID_GOOGLE_TOKEN`.
- Emails are matched case-insensitively and stored lower-case.

### Payments (feat/payments)
- **Changed** `POST /purchases`: with real payments on, creates (or re-uses) a Razorpay order and returns
  `gateway_config = {provider, key_id, order_id, amount, currency, name}` for Razorpay Checkout.
  Pressing "Pay" twice returns the same order. `502 GATEWAY_ERROR` if the provider is unreachable (safe to retry).
  Dev mode (`MOCK_PAYMENTS=true`) is unchanged: completes instantly, `gateway_config = {"mock": true}`.
- **New** `POST /purchases/{id}/verify` `{razorpay_order_id, razorpay_payment_id, razorpay_signature}`:
  call right after Checkout succeeds; returns the purchase as `completed`. `400 INVALID_SIGNATURE` otherwise.
- **Changed** `GET /purchases/{id}`: while a real payment is `pending` it asks the gateway, so a lost webhook never strands a paying user.
- **Changed** `POST /webhooks/payment`: now the real Razorpay webhook. Requires a valid `X-Razorpay-Signature`
  (`401 INVALID_SIGNATURE`), is idempotent by event id, understands `payment.captured`, `order.paid`, `payment.failed`.
  Not client-facing.
- **New error codes** `GATEWAY_ERROR` (502), `INVALID_SIGNATURE` (400/401), `INVALID_PAYLOAD` (400), `MOCK_MODE_ACTIVE` (400).

### Catalog, bookings, neighbourhoods (feat/catalog-bookings)
- **Changed** `GET /tours`: new query params `q` (search name/description/neighbourhood), `neighbourhood` (slug or id), `free`,
  `min_price`, `max_price` (paise), `sort` = newest|price_asc|price_desc|duration|popular, `limit` (1-100, default 50), `offset`.
  Items now include `neighbourhood {id,name,slug}` and `is_featured`.
- **New** `GET /tours/featured` - the "Featured walks" carousel.
- **Changed** `GET /tours/{id}`: adds `gallery_images[]`, `includes[]`, `languages[]`, `preview_audio_url` (signed, time-limited, public).
- **New** `GET /neighbourhoods?city=&include_empty=` and `GET /neighbourhoods/{id_or_slug}` (detail includes its tours with the caller's status). `404 NEIGHBOURHOOD_NOT_FOUND`.
- **New** `GET /purchases?tab=upcoming|past|all` - "My Bookings". Each row: `purchase_id, status (completed|refunded), amount_paise, purchased_at,
  tour{id,name,cover_image,duration_min,distance_km,neighbourhood}, walk_status (not_started|in_progress|completed), stops_visited, stop_count,
  session_id, device_bound, can_refund, refund_deadline`.
- **Changed** `POST /purchases/{id}/refund`: 14-day window (`REFUND_WINDOW_DAYS`) -> `409 REFUND_WINDOW_EXPIRED`; any started or completed walk -> `409 REFUND_NOT_ELIGIBLE`
  (all sessions are checked); refunds the payment at the gateway when real payments are on (`502 GATEWAY_ERROR`, nothing changed, safe to retry); clears the device binding.
- **Admin** `POST /admin/neighbourhoods`, `PUT /admin/neighbourhoods/{id}`; tour create/update accept `neighbourhood_id, is_featured, gallery_images, includes, languages, preview_audio_filename`; negative prices are rejected.
- Not supported by design: rescheduling a booking (a purchase is a one-time licence, not a time slot).

### Ratings, reviews, passport, profile (feat/ratings-passport)
- **New** `PUT /tours/{id}/rating` `{rating: 1-5}` (completed walkers only, re-rating updates) and `GET /tours/{id}/rating`
  -> `{avg_rating, rating_count, my_rating, distribution{1..5}}`. `403 TOUR_NOT_COMPLETED` if the walk is not finished.
- **Changed** `GET /tours` / `GET /tours/featured` items add `avg_rating`, `rating_count`; `sort=rating` added. `GET /tours/{id}` adds `my_rating`, `liked_by_me`.
- **Changed** `POST /tours/{id}/like` now requires a completed walk (`403 TOUR_NOT_COMPLETED`); `DELETE` returns `liked: false` (was wrongly `true`).
- **Changed** comments: max 1000 chars (`422`, previously a DB error), control characters stripped, blank rejected; `user_name` is "First L." only.
  Hidden (unpublished) tours return `404` for like/save/rate/comment.
- **New** `GET /reviews?tour_id=&limit=` - "What walkers say": newest comments with the author's star rating.
- **New** `GET /me/stats` -> `{walks_completed, distance_km, stops_visited, listening_minutes, neighbourhoods_stamped}`.
- **New** `GET /me/passport?city=` -> `{stamps_collected, total_neighbourhoods, stamps[{neighbourhood, cover_image, tours_total, tours_completed, stamped, stamped_at}]}`; stamped first.
- **New** `GET /sessions/{id}/summary` - the Walk-complete screen in one call (`stamp_earned`, ratings, `liked`, `commented`, stats). Owner only (`404 SESSION_NOT_FOUND` otherwise).

### Walk lifecycle (test/licensing)
- **Changed** `POST /sessions/{id}/events/batch`: events must reference stops of the session's own tour (`422 INVALID_STOP`).
- Behaviour now pinned by tests: starting twice resumes; completion consumes the licence (`403 TOUR_ALREADY_COMPLETED`, `409 SESSION_LOCKED`);
  device binding (`409 BOUND_TO_OTHER_DEVICE` on bind-device and package); kicked-out tokens get `401` while progress is kept.

### Frontend contract alignment (feat/contract-alignment)
Driven by `docs/FRONTEND_INTEGRATION.md`.
- **Changed** `POST /auth/signup`: **requires** `accepted_terms: true`; optional `marketing_opt_in` (default false). Stores `terms_accepted_at` + `terms_version`.
- **Changed (all endpoints)** validation errors (422) now use the standard envelope:
  `{"error": {"code": "VALIDATION_ERROR", "message": "email: ...", "fields": {"email": "...", "password": "..."}}}` (previously FastAPI's `{"detail": [...]}`).
- **Changed** numbers: `distance_km`, stop `lat`/`lng`, neighbourhood `centroid_lat/lng` are JSON numbers (were strings).
- **Changed** `GET /tours` items add `theme`, `difficulty`; `neighbourhood` adds `emoji`.
  New filters: repeatable `neighbourhood` and `theme`, `min_duration`, `max_duration` (minutes).
- **Changed** `GET /tours/{id}` adds `start_point`, `tags[]`, `preview_audio_title`, `neighbourhood_description`,
  `stops_preview[] = {order_index, name, blurb, icon}` (public teaser: never narration, audio or coordinates).
- **Changed** `GET /tours/{id}/package` stops add `blurb`, `icon`; `lat`/`lng` numeric.
- **Changed** `POST /purchases` on a **free** tour now creates a completed 0-paise purchase (`gateway_config = {"free": true}`);
  previously `400 TOUR_IS_FREE`. Repeat -> `409 TOUR_ALREADY_OWNED`. Free walks appear in My Bookings, can be cancelled (refund endpoint) before starting, and follow the one-playback rule.
  Walking a free tour without a claim still works.
- **Changed** bookings (`GET /purchases`) add `booking_ref` ("NOB-7KQ2M9XA"), `completed_at`, `my_rating`, `tour.theme`. `PurchaseOut` adds `booking_ref`.
- **Changed** `GET /me/passport?include_empty=true` (default): areas without a walk are listed as locked slots; each stamp adds `emoji`, `walk_name` (first walk completed there).
- **Changed** `GET /me/stats` adds `reviews_count` (ratings given).
- **Admin** tour create/update accept `theme, difficulty (Easy|Moderate|Hard), start_point, tags, preview_audio_title`; stop create accepts `blurb, icon`; neighbourhoods accept `tagline, emoji`.
- **Seed data** now mirrors the frontend: 4 walks, 12 neighbourhoods (8 locked passport slots). Coordinates, narration and tags are placeholders.

### Device recovery (feat/device-recovery)
- **New** `POST /purchases/{id}/rebind-device {device_identifier}` - moves a purchase bound to an old/lost/cleared device to the device the user is signed in on.
  The target must be the device of the current login (`400 DEVICE_MISMATCH`); only while the walk can still be played (`409 TOUR_ALREADY_COMPLETED`);
  one move per `REBIND_COOLDOWN_DAYS` (30) (`409 REBIND_COOLDOWN`, message gives the date). Binding an unbound purchase or "moving" to the same device is free.
  Walk progress is kept (sessions belong to the user, not the device).
- **Changed** `GET /purchases` rows add `device_status` (`unbound | this_device | other_device`) and `rebind_available_at` (set only while the cooldown runs).
  Show "Use on this device" when `device_status == "other_device"` and `rebind_available_at` is null.
- **Changed** `POST /sessions` now returns `409 BOUND_TO_OTHER_DEVICE` when the purchase is bound to a different device than the current login.
- **Changed** the `BOUND_TO_OTHER_DEVICE` message points to My Bookings instead of "re-download".

### Account (feat/account)
- **New** `GET /me` (same as `/auth/me`), `PATCH /me {full_name?, username?}` - username is stored lower-case, 3-30 of `a-z 0-9 _`, a leading `@` is stripped,
  `null` clears it, `409 USERNAME_TAKEN`. Email is not editable. `UserOut` now includes `username`, `notifications_enabled`, `analytics_opt_in`, `marketing_opt_in`.
- **New** `PATCH /me/preferences {notifications_enabled?, analytics_opt_in?, marketing_opt_in?}` (Settings toggles). Partial; returns the user.
- **New** `GET /me/export` - "Download my data": JSON attachment (profile, consent, purchases, walks, ratings, comments, likes, saved). No password hashes or tokens.
- **New** `DELETE /me {"confirm": "DELETE"}` -> 204. Erases comments, likes, ratings, saved tours and pending codes, anonymises the user row (email becomes `deleted-<id>@deleted.invalid`),
  signs out every device. Purchase, payment and walk records are kept for accounting, no longer tied to a person. The email can sign up again as a new account. Admins: `409 ADMIN_CANNOT_BE_DELETED`.
- **New** `POST /auth/forgot-password {email}` -> 200 with a generic message (identical for unknown emails; the code is only emailed if the account exists)
  and `POST /auth/reset-password {email, otp, new_password}` -> 204. Codes are single-use, expire (`OTP_TTL_SECONDS`), lock after `OTP_MAX_ATTEMPTS` wrong tries,
  and are bound to their purpose (a sign-in code cannot reset a password). A successful reset signs out all devices. Same error codes as OTP sign-in.
- Internal: sign-in codes now share one service with reset codes (`otp_requests.purpose`).

### Notifications (feat/notifications)
In-app only (no push in v1). Created automatically, idempotently, and skipped for users who turned notifications off (`PATCH /me/preferences`).
- **New** `GET /me/notifications?limit=50&unread_only=false` -> `{unread_count, items[{id, type, title, subtitle, tour_id, is_read, created_at}]}`, newest first.
  `unread_count` covers all notifications (drives the bell dot), not just the page.
- **New** `POST /me/notifications/{id}/read` (returns the item), `POST /me/notifications/read-all` (204), `DELETE /me/notifications/{id}` (204, the swipe-to-dismiss). `404 NOTIFICATION_NOT_FOUND` also for other people's ids.
- Types: `confirmed` ("You're in!", on purchase completed incl. free claims and verified payments, once per purchase), `review` ("How was your walk?", when a walk is completed, once per walk),
  `new` ("New walk: <name>", subtitle "Malleshwaram · 2.3km · ₹249", sent to all walkers when an admin first publishes a tour), `reminder` (reserved; needs a scheduler, not generated yet).
- Account deletion erases a user's notifications.

