# Deployment (staging)

Status: configuration written; **not run end to end** (no Docker daemon in the build environment). Do a first deploy on a throwaway server and fix what it finds.

## What runs
`docker-compose.yml`: `db` (Postgres 16, private), `backend` (FastAPI; applies migrations on start), `nginx` (80/443, TLS, rate limit, serves `/media/`).

## Before the first start
1. DNS for your domain points at the server.
2. Root `.env` (copy `.env.example`): set `DB_PASSWORD` (compose refuses to start without it).
3. `backend/.env` (copy `backend/.env.example`) with staging values:
   - `ENVIRONMENT=staging`, `DEBUG=false`
   - `SECRET_KEY`: new random value (`python -c "import secrets; print(secrets.token_urlsafe(48))"`). Never reuse a dev key.
   - `MEDIA_SIGNING_KEY`: a different random value.
   - `MOCK_PAYMENTS=false` with `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` (test-mode keys are fine for staging).
   - `EMAIL_BACKEND=smtp` with `SMTP_*`, `EXPOSE_DEV_OTP=false`.
   - `ADMIN_PASSWORD`: strong; `ALLOWED_ORIGINS`: your real frontend origin(s) only; `BASE_URL`: the public https URL.
4. TLS certificate: put `cert.pem` and `key.pem` in `./certs` (or set `CERT_DIR`). Let's Encrypt via certbot works; the ACME path is already routed.

The app refuses to boot in staging/production if it detects unsafe settings (weak secret, mock payments, dev OTP, console email, debug on).

## Start
```
docker compose up -d --build
docker compose logs -f backend      # migrations run first
curl -k https://localhost/health
docker compose exec backend python -m app.seed   # demo data, staging only
```
Razorpay webhook URL: `https://<domain>/webhooks/payment`.

## Known gaps
- Media is on local disk (`backend/media`), served by nginx. For scale, move audio to object storage + CDN (the signed-URL layer is the seam to change).
- Auth rate limits are shared across workers and containers (Postgres table `rate_limit_hits`, `RATE_LIMIT_BACKEND=auto` → postgres outside development). A fixed window can allow up to 2x the limit across a minute boundary.
- No backups configured: schedule `pg_dump` and back up `backend/media`.
- No monitoring or error tracking yet.
- Placeholder audio and seed data must be replaced with real content.
