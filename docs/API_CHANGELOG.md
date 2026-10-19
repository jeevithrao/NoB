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
