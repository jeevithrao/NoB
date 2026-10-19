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
_(add entries here as chunks land)_
