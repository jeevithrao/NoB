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
