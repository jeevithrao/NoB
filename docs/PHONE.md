# Running NoB on a phone (PWA)

NoB runs as a Progressive Web App: the website opens in the phone's browser and can be installed to the home screen (no app store). Built in `frontend/` (manifest, service worker, icons). Status: verified in desktop Chromium (manifest, service worker, app shell loads offline). **Not yet tested on a real iPhone or Android phone.**

## What works / limits
| | |
|---|---|
| Install | Android Chrome: "Install app". iPhone Safari: Share, then "Add to Home Screen". |
| HTTPS | Required for install, service worker and GPS on any address except `localhost`. |
| Audio | After you start a walk, all stop audio is downloaded and cached on the phone, so it keeps playing without signal. |
| Start of a walk | The app first shows the way to the starting point (street route, distance, Google Maps link). The **Start walk** button appears when you are within the stop's trigger radius; the walk is only recorded as started when you tap it. In development builds a "Testing only" button skips this. If location is off, an "I'm at the start" button is shown instead. |
| Offline | After one online start the walk is saved on the phone and can be started and finished offline; events sync when the connection returns. |
| GPS | Only while the app is open on screen. The app asks the browser to keep the screen awake during a walk. iOS may be stricter: test it. |
| Maps | Tiles load from OpenStreetMap while online and are cached briefly. |
| Icons | Placeholder icons (`frontend/public/icons`). Replace with real branding. |

## Test on your own phone, today
1. Start the API and the frontend on your computer (see `docs/INTEGRATION.md`).
2. Give the phone an HTTPS address. Easiest: a tunnel, e.g. `cloudflared tunnel --url http://localhost:5173` (and a second one for the API on port 8000), or ngrok.
3. Set `frontend/.env` to `VITE_API_URL=<the API's https tunnel URL>`, build (`npm run build && npm run preview -- --host`) or run dev, and add the frontend's https URL to the backend's `ALLOWED_ORIGINS`.
4. Open the frontend URL on the phone, sign up, buy a walk (mock payments), start it, and allow location.

Android over USB, no tunnel: `adb reverse tcp:5173 tcp:5173 && adb reverse tcp:8000 tcp:8000`, then open `http://localhost:5173` on the phone (localhost counts as secure).

## Before real users
Real HTTPS domain, real Razorpay keys, a test on iPhone and Android, real icons, and a decision on offline start. See `docs/DEPLOYMENT.md`.
