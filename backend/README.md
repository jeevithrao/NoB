# NoB Backend

FastAPI backend for the Neighbourhoods of Bangalore audio walking-tour app.

## What's implemented

- **Auth** — signup/login (email+password), JWT access + refresh tokens,
  single-active-session enforcement (logging in on a new device kicks the old
  one out — see `dependencies.py` / `routers/auth.py`).
  Email OTP sign-in (`/auth/request-otp`, `/auth/verify-otp`) and Google
  sign-in are implemented. OTP codes are **emailed** (SMTP) — set
  `EMAIL_BACKEND=console` and `EXPOSE_DEV_OTP=true` in development to read them
  from the server log / response. Auth endpoints are rate-limited.
- **Tours** — catalog (`GET /tours`), detail, and the offline download
  manifest (`GET /tours/{id}/package`) with per-user status
  (`not_purchased` / `purchased` / `in_progress` / `completed_locked`).
- **Purchases** — `POST /purchases` completes instantly while
  `MOCK_PAYMENTS=True` (default), so the whole purchase → download → walk
  flow is testable with zero payment-gateway setup. Device binding and the
  `409 BOUND_TO_OTHER_DEVICE` conflict are real. Swap in Razorpay/Stripe by
  filling in the "real-gateway path" in `routers/purchases.py`.
- **Sessions (walks)** — start/resume, idempotent offline event-batch sync
  (`client_event_id` dedupe), and `complete` — which is the moment the
  one-lifetime-use license actually locks (`purchases.is_locked`).
- **Social** — saved tours (wishlist), likes, comments (comments require a
  completed walk, per the business rules doc).
- **Admin** — create/update/publish tours, add stops, list purchases, and a
  support tool to reset a stuck session.

Every endpoint returns errors as `{"error": {"code", "message"}}` per the API
spec doc.

## Local setup

```bash
# 1. Postgres (either docker-compose from repo root, or a local install)
docker compose up -d

# 2. Python env
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Config
cp .env.example .env
# edit .env if your DB creds differ from the docker-compose defaults

# 4. Schema — Alembic builds everything from an empty database
#    (no hand-applied SQL). Existing pre-baseline local DBs must be recreated:
#    docker compose down -v && docker compose up -d
alembic upgrade head

# 5. Seed a few real Bangalore tours + an admin user
#    Set ADMIN_EMAIL / ADMIN_PASSWORD in .env, or a random password is
#    generated and printed once.
python -m app.seed

# 6. Generate real (robotic but genuinely playable) narration audio for
#    every seeded stop, via espeak-ng + ffmpeg — swap for real recordings
#    before shipping, but this makes the whole download -> GPS trigger ->
#    playback -> audio_started/finished pipeline testable today instead
#    of hitting a 404 on every stop.
apt-get install -y espeak-ng ffmpeg   # if not already installed
python -m app.generate_audio

# 7. Run
uvicorn app.main:app --reload
```

Swagger UI: http://localhost:8000/docs

## Project layout

```
app/
  core/security.py     # password hashing, JWT issue/verify
  dependencies.py       # get_current_user / get_current_admin / optional-auth
  models/               # SQLAlchemy models (already existed, unchanged)
  schemas/              # Pydantic request/response models
  routers/              # auth, tours, purchases, sessions, social, admin
  seed.py               # demo data
```

## Known gaps / next steps

- Real object storage (S3) for audio — currently serves from `media/` locally;
  the one seam to change is `_signed_audio_url()` in `routers/tours.py`.
  Audio itself is currently robotic TTS (`python -m app.generate_audio`),
  real enough to test playback end-to-end but not real narration — swap for
  professionally recorded audio before shipping.
- Real payment gateway integration (Razorpay recommended per the docs).
- Refund time window (14 days) — tracked in `docs/BACKEND_PLAN.md`.
