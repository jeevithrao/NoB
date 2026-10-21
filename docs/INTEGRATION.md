# Connecting the frontend to the backend (local)

## 1. Start the backend
```
cd backend
cp .env.example .env     # then set DATABASE_URL, SECRET_KEY, ADMIN_PASSWORD
alembic upgrade head
python -m app.seed       # demo neighbourhoods, walks, stops
python -m app.generate_audio   # placeholder audio (media/audio)
uvicorn app.main:app --reload --port 8000
```
Local dev flags: `MOCK_PAYMENTS=true`, `EXPOSE_DEV_OTP=true`, `ALLOWED_ORIGINS=http://localhost:5173`.
Docs UI: http://localhost:8000/docs

## 2. Point the frontend at it
In `nob-react/`: copy `docs/frontend-kit/api.js` to `src/api.js`, add `.env` with `VITE_API_URL=http://localhost:8000`, then run `npm run dev` (port 5173). Replace `data.js` reads with `api.*` calls using the table in `docs/frontend-kit/README.md`.

## 3. Check both sides agree
`node docs/frontend-kit/smoke.mjs` (full journey) and `python backend/scripts/smoke_e2e.py`.

## Contract
`docs/openapi.json` is the machine-readable API contract (import it into Postman/Insomnia, or generate types with `openapi-typescript`). Regenerate with `python backend/scripts/export_openapi.py`; a test fails if it is stale.

## Not verified here
Docker/nginx were not run in this environment, and real Razorpay needs keys. Both need a check on your machine.
