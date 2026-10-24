# NoB — Neighbourhoods of Bangalore (React)

React + Vite port of NOB_Final4.html. All 17 screens, the same CSS (copied verbatim), the same data, animations and interactions.

    npm install
    npm run dev

## Place photos
Drop images into `public/images/` (or paste URLs into `src/images.js`):

| Place        | Main photo           | Gallery (detail page)                                   |
|--------------|----------------------|---------------------------------------------------------|
| Malleshwaram | malleshwaram.jpg     | malleshwaram-1.jpg, -2.jpg, -3.jpg                      |
| Basavanagudi | basavanagudi.jpg     | basavanagudi-1.jpg, -2.jpg, -3.jpg                      |
| Cubbon Park  | cubbon-park.jpg      | cubbon-park-1.jpg, -2.jpg, -3.jpg                       |
| MG Road      | mg-road.jpg          | mg-road-1.jpg, -2.jpg, -3.jpg                           |

Photos are loaded from each place's Wikipedia article automatically (no key). Put your own files above to override them. Missing photos fall back to the emoji tile.

## Layout modes
- Desktop: the app is shown inside a 320×680 phone frame with the prototype nav row above it.
- Phones (viewport ≤ 600px wide): the app fills the screen (100dvh), respects safe-area insets, and the frame, notch, caption and prototype nav row are hidden.

## Things to verify before launch
- Stop coordinates (`coords` in `src/data.js`), difficulty labels, audio-sample titles, tags and review counts are placeholders.
- Active Walk uses Leaflet + OpenStreetMap tiles (no API key). Audio playback is simulated.
- Settings → Photo credits lists the Wikipedia article behind each place photo.

## Live mode (backend connected)
Set `VITE_API_URL` (copy `.env.example` to `.env`) and the app loads real data from the API; leave it unset and it runs as the original prototype with `src/data.js`.
- `src/api.js`: API client (tokens, device id, errors). `src/live.js`: loads API data into the arrays the screens already use.
- The backend must allow the dev origin, e.g. `ALLOWED_ORIGINS=http://localhost:5173` (use `localhost`, not `127.0.0.1`).
- Wired: sign up, log in, log out, catalogue, walk detail with real audio sample, buy (mock payments), bookings, cancel, move to this device, passport, notifications, profile, settings (preferences, export, delete).
- Also wired: sign in with an emailed code, forgot/reset password, "Leave review" on past bookings, and Google sign-in (set `VITE_GOOGLE_CLIENT_ID`; without it the button explains it is not set up).
- Not wired yet: Razorpay checkout (pay button works with mock payments only).
- Walking (live): downloads and caches every stop's audio, plays real audio, advances on arriving inside a stop's trigger radius (or "Next stop"), batches `arrived` / `audio_started` / `audio_finished` events, keeps the screen awake, and completes the walk with rating, like and comment on the finish screen. Ending early asks for confirmation, because a completed walk cannot be replayed.
- PWA: installable, offline app shell, cached walk audio. See `../docs/PHONE.md`. The service worker only registers in production builds (`npm run build`).

## Offline walks
The first online start of a walk saves its package (stops, coordinates, audio links) on the phone and the audio in the Cache API. After that the walk can be started and finished with no signal: events and completion are kept in `localStorage` (`nob.pending`) and sent when the connection returns (`online` event or next app start). Limits: the catalogue itself still needs a connection to load after a full page reload, and rating/liking needs a connection. Test: `python3 frontend/e2e/offline_walk.py`.
