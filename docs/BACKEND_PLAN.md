# Backend plan — 3 days

Scope: **backend only** (`backend/`, `docs/`). Frontend is built by a partner from the UI screenshots.
Decisions: email-only OTP · no "Reschedule" · 14-day refund window · mock payments + real signature-verified
Razorpay webhook path (no keys needed until go-live) · keep existing repo, harden it.

Status legend: ⬜ todo · 🟦 in progress · ✅ done

## Day 1 — Safe and reproducible
| # | Chunk | Branch | Status |
|---|---|---|---|
| 0 | Repo structure, docs folder, CONTRIBUTING | `feat/repo-structure` | ✅ |
| 1 | Close OTP account-takeover, auth hardening, rate limits | `fix/otp-takeover` | ✅ |
| 2 | Alembic baseline from models + neighbourhoods + completed-session partial index | `feat/db-baseline` | ✅ |
| 3 | pytest harness, auth/device tests, CI | `test/harness-and-auth` | ✅ |

**Checkpoint 1** (`v0.2-cp1`) ✅ secure auth, DB rebuildable from Alembic, 58 passing tests, CI workflow.

## Day 2 — Money and screens
| # | Chunk | Branch | Status |
|---|---|---|---|
| 4 | Razorpay order + signature-verified idempotent webhook (mock fallback) | `feat/payments` | ✅ |
| 5 | `GET /purchases` (bookings), refund window, neighbourhood endpoints, tour search/filters | `feat/catalog-bookings` | ✅ |
| 6 | Ratings, passport (stamps) and profile-stats endpoints | `feat/ratings-passport` | ✅ |
| 7 | Licensing tests: duplicate purchase, replayed webhook, consumed tour, resume, kick-out, admin 403 | `test/licensing` | ✅ |

**Checkpoint 2** (`v0.2-cp2`) ✅: buy → download → walk → complete passes in tests.

## Day 3 — Account and ship
| # | Chunk | Branch | Status |
|---|---|---|---|
| 8 | Forgot password, delete account, data export, consent flags | `feat/account` | ⬜ |
| 9 | Notifications stub, admin refund/reset rules, error-code audit vs API spec | `feat/admin-errors` | ⬜ |
| 10 | Staging deploy config (docker, nginx, TLS), S3 seam, Postman collection | `chore/deploy` | ⬜ |
| 11 | README + docs brought in line with code | `docs/final-sync` | ⬜ |

**Checkpoint 3** (`v0.2.0`): staging-ready, partner can integrate.

## Screen → API map (from the screenshots)
| Screen | Backend |
|---|---|
| Sign up (terms + marketing consent) | `POST /auth/signup` + consent flags |
| Sign in / Google / OTP / forgot password | `/auth/login`, `/auth/google`, `/auth/request-otp`, `/auth/verify-otp`, `/auth/forgot-password`, `/auth/reset-password` |
| Explore (featured, by neighbourhood, what walkers say) | `GET /tours`, `GET /neighbourhoods`, `GET /reviews/featured` |
| All walks (search, filters) | `GET /tours?q=&neighbourhood_id=&max_price=` |
| Tour detail | `GET /tours/{id}` |
| My bookings (upcoming / past) | `GET /purchases` |
| My passport (stamps) | `GET /me/passport` |
| Neighbourhood detail | `GET /neighbourhoods/{id}` |
| Downloads | `GET /tours/{id}/package`, `POST /purchases/{id}/bind-device` |
| Notifications | `GET /me/notifications` (stub) |
| Active walk / walk complete (rating, like, comment) | `/sessions/*`, `POST /tours/{id}/rating`, likes, comments |
| Profile (stats) | `GET /me/stats` |
| Settings (delete account, download my data, analytics opt-in) | `DELETE /me`, `GET /me/export`, `PATCH /me/preferences` |
