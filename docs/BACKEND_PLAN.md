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

## Day 3 — Frontend contract, account, ship (revised after the frontend arrived)
Decisions (D1-D8): ship web/PWA first; free walks = 0-paise claim; web device recovery = one self-service re-bind per 30 days;
purchases never expire; in-app notifications only; images local/free for now (owned later); mock payments until keys exist;
cancellation rules unchanged (14 days, not started).

| # | Chunk | Branch | Status |
|---|---|---|---|
| 8 | Contract alignment: new fields, public stop preview, filters, free claims, booking refs, consent, error envelope, seed mirrors frontend | `feat/contract-alignment` | ✅ |
| 9 | Device recovery (re-bind) + require device on walk start | `feat/device-recovery` | ✅ |
| 10 | Account: PATCH /me (+username), preferences, export, delete (anonymise), forgot/reset password | `feat/account` | ✅ |
| 11 | In-app notifications | `feat/notifications` | ✅ |
| 12 | Integration kit: OpenAPI export, Postman, docker-compose, reference `api.js`, smoke script | `chore/integration` | 🟦 smoke script done |
| 13 | Staging deploy config, final docs sync | `chore/deploy` | ⬜ |

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
