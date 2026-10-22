# Run guide: from "frontend connected" to launch

Each stage says what to run, what you should see, and what "done" means. Stages 1-3 were tested in this project; 4-7 need your keys, phone or server.

## 1. Whole app on your computer (mock payments)
```
# terminal 1: backend  (Postgres 16 running; DB created once: createdb nob_dev)
cd backend && source ../venv/bin/activate
cp .env.example .env            # set DATABASE_URL(_SYNC), SECRET_KEY, ADMIN_PASSWORD; keep MOCK_PAYMENTS=true, EXPOSE_DEV_OTP=true
alembic upgrade head && python -m app.seed && python -m app.generate_audio
uvicorn app.main:app --reload --port 8000

# terminal 2: frontend
cd frontend && cp .env.example .env     # VITE_API_URL=http://localhost:8000
npm install && npm run dev              # open http://localhost:5173  (use "localhost", not 127.0.0.1)
```
Done when you can sign up, buy a walk, walk it, finish it, and see the stamp. Checks: `node docs/frontend-kit/smoke.mjs` (API journey) and `cd backend && pytest -q`.

## 2. Payments with the fake Razorpay (tests our code path, no keys)
```
python backend/scripts/fake_razorpay.py                     # :9000
# restart the API with:
RAZORPAY_API_BASE=http://localhost:9000/v1 RAZORPAY_KEY_ID=rzp_test_fake RAZORPAY_KEY_SECRET=fakesecret \
RAZORPAY_WEBHOOK_SECRET=fakewebhook MOCK_PAYMENTS=false uvicorn app.main:app --port 8000
python3 frontend/e2e/payment_flow.py                        # needs: pip install playwright
```
Done when it prints dismissed / declined / invalid-signature messages, then "You're in!" and the booking.

## 3. Real Razorpay TEST keys (your keys)
Follow `docs/RAZORPAY_SETUP.md` to get keys. Put them in `backend/.env` with `MOCK_PAYMENTS=false`, restart the API, run the frontend as in stage 1, buy a paid walk and pay with Razorpay's test card/UPI details from their docs. Done when the purchase becomes "completed" and the booking appears.
Webhook (optional for the first test, needed before launch): expose the API (`cloudflared tunnel --url http://localhost:8000` or `ngrok http 8000`), then add `https://<tunnel>/webhooks/payment` in the Razorpay Dashboard with your webhook secret. Never paste the Key Secret into chat or commit it.

## 4. A real phone (iPhone and Android)
Follow `docs/PHONE.md`: two HTTPS tunnels (API and frontend), set `VITE_API_URL` to the API tunnel, add the frontend tunnel URL to `ALLOWED_ORIGINS`, `npm run build && npm run preview -- --host`, open it on the phone. Test: install to home screen, sign up, buy, walk outside (GPS), lock/unlock the screen, airplane mode mid-walk, finish. Note every failure; GPS in the background and screen-awake on iPhone are the likeliest.

## 5. Real content
Replace placeholders: real stop coordinates, narration audio (record or text-to-speech), photos you own, `cover_image`/`gallery_images`. Admin endpoints (see `/docs`) publish tours. Done when a stranger can walk a real route with the app alone.

## 6. Staging server
Follow `docs/DEPLOYMENT.md` (domain, HTTPS certificate in `./certs`, `.env` files, `docker compose up -d --build`). First Docker run has never been done: expect small fixes. Done when the phone test from stage 4 passes against the staging URL with real email (SMTP) and Razorpay test keys.

## 7. Launch
Legal pages live (privacy, terms, refund, grievance email), Razorpay LIVE keys after their verification, backups (`pg_dump` + media), error monitoring, a tested restore, and a founder sign-off. See the founder checklist.
