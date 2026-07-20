# NoB Mobile (Expo / React Native)

Screen skeleton for the NoB audio walking-tour app, wired to the FastAPI
backend in `../backend`.

## What's implemented

- **Auth** — signup/login, session persisted locally, device id generated
  once per install and reused for every request that needs one.
- **Home feed** — tour catalog with live status per tour.
- **Tour detail** — status-aware call to action (Buy → Download → Continue
  walk → Completed), like button, comments (posting gated on having
  completed the walk, same as the backend).
- **Download** — fetches the offline package, binds the purchase to this
  device, downloads each stop's audio for offline playback.
- **Route to start** — one-time distance check to the first stop before the
  walk begins.
- **Active walk** — watches GPS in the background, triggers stop audio when
  you enter a stop's radius, and queues progress events **locally first**
  (`src/api/offlineStorage.ts`) so a dead zone never loses progress — they
  sync to the backend opportunistically and are safe to resend thanks to
  `client_event_id`.
- **Walk complete** — leave a comment, back to the catalog.

## Setup

```bash
cd mobile
npm install
```

Edit `src/api/constants.ts` → `API_BASE_URL`:
- Physical device or iOS simulator on the same Wi-Fi as your dev machine:
  use your machine's LAN IP, e.g. `http://192.168.1.23:8000`.
- Android emulator: `http://10.0.2.2:8000` reaches the host machine.
- Or run `npx expo start --tunnel` and use the tunnel's forwarded URL.

Then:

```bash
npm start        # opens Expo dev tools / QR code
npm run android   # or
npm run ios
```

Make sure the backend (`../backend`) is running and seeded
(`python -m app.seed`) first, or the catalog will be empty.

## Known gaps / next steps

- **Audio files aren't hosted yet** — the seed data references filenames
  like `malleshwaram/01-circle.mp3` but nothing serves them yet. Download
  falls back to the raw remote URL on failure so the rest of the flow
  (GPS trigger, playback attempt, event logging) still runs; drop real
  files into `backend/media/audio/<path>` to make playback work end to end.
- **Background location** — `expo-location`'s `watchPositionAsync` here only
  runs while the app is foregrounded/backgrounded-but-alive. True
  killed-app background tracking needs `startLocationUpdatesAsync` with a
  background task registered — worth adding once the core loop is validated.
- **Refresh-token rotation** — `/auth/refresh` exists on the backend but the
  app doesn't yet call it on 401; requests just fail once the access token
  expires (60 min by default) until the user logs in again.
- **Payments** — purchase flow assumes `MOCK_PAYMENTS=True` on the backend;
  there's no Razorpay SDK wired in here yet.
- Push notifications, saved-tours/wishlist screen, and a proper onboarding
  flow aren't built yet either.
