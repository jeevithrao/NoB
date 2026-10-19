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
