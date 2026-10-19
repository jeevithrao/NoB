# API Specification — v1

Base URL: `https://api.neighbourhoodsofbangalore.com/v1` (placeholder)
Auth: Bearer token (JWT) in `Authorization` header, issued at login, tied to an `auth_sessions` row (see Security doc for invalidation rules).

> This is the original design spec. Endpoints added or changed during implementation are tracked in
> [`docs/API_CHANGELOG.md`](../API_CHANGELOG.md) and should be folded back in here.

---

## Auth

### `POST /auth/signup`
Body: `{ email, password, full_name, device_identifier }`
Returns: `{ user_id }` → triggers OTP flow (email or SMS, TBD by devs based on chosen provider).

### `POST /auth/verify-otp`
Body: `{ user_id, otp_code }`
Returns: `{ access_token, user }`
Side effect: creates `devices` row if `device_identifier` unseen, creates `auth_sessions` row, invalidates any other active session for this user.

### `POST /auth/login`
Body: `{ email, password, device_identifier }`
Returns: `{ access_token, user }`
Side effect: same session invalidation as above.

### `POST /auth/google`
Body: `{ google_id_token, device_identifier }`
Returns: `{ access_token, user }`

### `POST /auth/logout`
Invalidates the current `auth_sessions` row.

---

## Tours

### `GET /tours?city=Bangalore`
Returns list of published tours: `id, name, description, cover_image, duration_min, distance_km, price_paise, neighbourhood, user_status` (`not_purchased | purchased | in_progress | completed_locked`).

### `GET /tours/{id}`
Full tour detail, including per-user `status` as above.

### `GET /tours/{id}/package`
**Requires:** valid completed purchase for this user+tour.
Returns: stop manifest (ordered list with lat/lng, trigger_radius_m, narrative_text) + signed audio URLs.
Errors: `403` if not purchased; `409` if bound to a different device (see Feature Spec 3).

---

## Purchases

### `POST /purchases`
Body: `{ tour_id }`
Returns: `{ purchase_id, gateway_order_id, gateway_config }`
Errors: `409` if user already has a `completed` purchase for this tour.

### `GET /purchases/{id}`
Returns current status — used as a fallback poll if a webhook is delayed.

### `POST /purchases/{id}/bind-device`
Body: `{ device_identifier }`
Sets `bound_device_id` on first download. Errors `409` if already bound to a different device.

### `POST /webhooks/payment` (gateway → server, not client-facing)
Verifies signature, updates purchase status to `completed` or `failed`.

---

## Sessions (walks)

### `POST /sessions`
Body: `{ tour_id }`
Returns existing non-completed session if one exists (resume), otherwise creates a new one.
Errors: `403` if tour has a `completed` session already for this user (license consumed).

### `POST /sessions/{id}/events/batch`
Body: `{ events: [{ client_event_id, stop_id, event_type, occurred_at }, ...] }`
Idempotent — dedupes by `client_event_id`. Updates `stops_visited` accordingly.

### `POST /sessions/{id}/complete`
Marks `completed = TRUE`, `completed_at = NOW()`. Locks the tour per licensing rules.

---

## Saved Tours / Likes / Comments

### `POST /saved-tours` / `DELETE /saved-tours/{tour_id}`
### `POST /tours/{id}/like` / `DELETE /tours/{id}/like`
### `POST /tours/{id}/comments`
Body: `{ comment_text }`. Server checks the user has a `completed` session for this tour before allowing (see Feature Spec / Business Rules).
### `GET /tours/{id}/comments`

---

## Admin (separate auth scope — `role = 'admin'` required)

### `POST /admin/tours` / `PUT /admin/tours/{id}` / `POST /admin/tours/{id}/publish`
### `POST /admin/tours/{id}/stops` — upload stop data + audio file
### `GET /admin/purchases` — search/filter all purchases
### `POST /admin/sessions/{id}/reset` — support tool to reset a stuck session (GPS bug recovery, per Business Rules doc)

---

## Error format (all endpoints)

```json
{
  "error": {
    "code": "TOUR_ALREADY_OWNED",
    "message": "You already own this tour."
  }
}
```
Standard HTTP status codes apply (`400`, `401`, `403`, `404`, `409`, `500`). Error `code` values should be a fixed enum shared with frontend devs — full list to be finalized during implementation, not guessed here.
