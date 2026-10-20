# Database

PostgreSQL 16. The schema is built **only** by Alembic (`backend/alembic/versions`). Never apply SQL by hand.

```bash
cd backend
alembic upgrade head                              # build / update
alembic revision --autogenerate -m "what changed" # after editing a model
alembic check                                     # fails if models and migrations drifted
```
CI runs the upgrade → downgrade → upgrade round trip and a drift test (`tests/test_database.py`).

## Migrations
| Rev | What |
|---|---|
| `0001` | Baseline: users, user_login_sessions, otp_requests, tours, stops, purchases, tour_sessions, session_events, saved_tours, tour_likes, tour_comments |
| `0002` | `neighbourhoods` + `tours.neighbourhood_id`, one-completed-session partial unique index, CHECK constraints |
| `0003` | `payment_events` (webhook deliveries, unique event id) |
| `0004` | tour catalog fields: `is_featured`, `gallery_images`, `includes`, `languages`, `preview_audio_filename` |
| `0005` | `tour_ratings` (1-5, one per user and tour) |
| `0006` | frontend contract: tour `theme/difficulty/start_point/tags/preview_audio_title`, stop `blurb/icon`, neighbourhood `tagline/emoji`, `purchases.booking_ref`, user consent columns |
| `0007` | `purchases.device_rebound_at` (self-service device move allowance) |
| `0008` | `users.username` (unique, lower-case), `notifications_enabled`, `analytics_opt_in`, `deleted_at`; `otp_requests.purpose` |
| `0009` | `notifications` (per-user, unique `dedupe_key` for idempotent creation) |

> The pre-baseline migration chain was replaced (it diffed against a hand-applied SQL file and could not build an empty DB).
> A local database created before `0001` must be recreated.

## Tables
| Table | Purpose |
|---|---|
| `users` | Accounts. `role` ∈ user/admin (CHECK). Emails stored lower-case. |
| `user_login_sessions` | One row per login; `is_active` flipped off when the user signs in elsewhere (single-session rule). Holds the refresh token. |
| `otp_requests` | Email OTPs: keyed-HMAC hash, attempt counter, expiry, used flag. |
| `neighbourhoods` | Areas that group tours (name, slug, description, cover image, centroid). |
| `tours` | Catalog. Money is integer `price_paise`. `neighbourhood_id` → neighbourhoods. |
| `stops` | Ordered stops with lat/lng, trigger radius, narration text and audio file. |
| `purchases` | One per (user, tour) attempt. `status` ∈ pending/completed/failed/refunded. `device_id` = bound device. `is_locked` = licence consumed. |
| `tour_sessions` | A walk. `completed` = licence consumed. |
| `session_events` | Idempotent walk events (`client_event_id` unique). |
| `saved_tours`, `tour_likes`, `tour_comments` | Wishlist, likes, comments (soft delete). |

## Constraints that carry the licensing model
- `idx_one_active_purchase_per_user_tour` — a user can hold only one pending/completed purchase per tour (failed/refunded rows don't block a re-buy).
- `idx_one_completed_session_per_user_tour` — at most one completed walk per (user, tour), enforced by the DB, not just the API.
- CHECKs on role, price, purchase status/amount, trigger radius, stops_visited, event type, comment length.

## Design vs implementation
| Design doc (`design/03-schema-extensions.sql`) | Implemented as |
|---|---|
| `devices` + `auth_sessions` | `user_login_sessions.device_id` (string). Same behaviour; a user-visible device list is not needed by any screen. |
| `purchases.bound_device_id` (FK) | `purchases.device_id` (string identifier). |
| `neighbourhoods`, `tours.neighbourhood_id` | As designed, plus a `slug`. |
| Legacy SQL triggers (lock purchase on completion, deactivate old sessions) | Done in application code inside one transaction, covered by tests. |

Legacy raw SQL is kept for reference at `docs/reference/Nob_schema_v2_legacy.sql`.
