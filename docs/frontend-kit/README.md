# NoB frontend kit

`api.js` is a ready-made client for the NoB API (plain `fetch`, no dependencies). Copy it to `src/api.js` in the React app.
`smoke.mjs` runs a full user journey through it against a live API (35 steps) and is the quickest way to check the two sides still agree.

```js
import { createApi, formatPrice, metaLine } from './api'
export const api = createApi({
  baseUrl: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  onSessionEnded: reason => { /* 'other_device' | 'expired' -> show login */ },
})
```

Set `VITE_API_URL=http://localhost:8000` in `.env`. The API must allow the dev origin: `ALLOWED_ORIGINS=http://localhost:5173`.

## Screen -> call

| Screen | Calls |
|---|---|
| Sign up / log in | `auth.signup` (needs `acceptedTerms: true`), `auth.login`, `auth.google` |
| OTP / forgot password | `auth.requestOtp` + `auth.verifyOtp`; `auth.forgotPassword` + `auth.resetPassword` |
| Explore + filters | `tours.list({ theme, neighbourhood, free, maxDuration, sort, q })`, `tours.featured` |
| Neighbourhoods | `neighbourhoods.list`, `neighbourhoods.detail(slug)` |
| Walk detail | `tours.detail(id)`, audio sample via `mediaUrl(detail.preview_audio_url)`, `reviews.recent({tourId})` |
| Buy | `purchases.buy(id)` (mock: instantly `completed`), then `purchases.bindDevice(purchase_id)` |
| Bookings tabs | `purchases.bookings('upcoming' \| 'past')`; cancel = `purchases.cancel` |
| Before walking | `tours.package(id)` -> stops with coordinates + signed `audio_url` |
| Walking | `sessions.start`, `sessions.sendEvents`, `sessions.complete`, `sessions.summary` |
| After the walk | `social.rate`, `social.like`, `social.comment` |
| Saved | `social.save / unsave / saved` |
| Passport / Profile | `me.passport`, `me.stats`, `me.profile`, `me.update`, `me.preferences` |
| Bell | `notifications.list` (`unread_count`, `items`), `markRead`, `markAllRead`, `dismiss` |
| Settings | `me.exportData`, `me.deleteAccount` |
| "Walk is on another device" | `purchases.rebindDevice(id)` (once per 30 days) |

## Things the screens must handle
- Errors are `ApiError` with `.code` (e.g. `TOUR_NOT_OWNED`, `BOUND_TO_OTHER_DEVICE`, `TOUR_ALREADY_COMPLETED`, `USERNAME_TAKEN`) and `.fields` for `VALIDATION_ERROR`.
- Prices are paise, distance km, duration minutes. Use `formatPrice`, `metaLine`.
- `average_rating` can be `null` (no ratings yet): hide the stars.
- Image fields (`cover_image`, `gallery_images`) may be empty: keep the local image fallback until they are filled.
- Each browser is one device. Clearing site data makes a new device; use `rebindDevice`.
- Only one login at a time: a new login elsewhere triggers `onSessionEnded('other_device')`.

## Run the check
```
node docs/frontend-kit/smoke.mjs http://localhost:8000
```
Needs the API running with `MOCK_PAYMENTS=true`.
