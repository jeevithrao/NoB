# NoB Web

Browser-based alternative to the mobile app — browse, buy, and walk tours
without installing anything. Same backend, same business rules.

## Design system

Built around real material culture from old Bangalore, deliberately avoiding
the generic "warm cream + terracotta" AI-design default:

| Token | Hex | Grounded in |
|---|---|---|
| `chunam` | `#EFE7D8` | Limewash plaster on old bungalow walls — base background |
| `kaapi` | `#2B1D14` | Filter coffee — primary text ink |
| `oxide` | `#9A3324` | Red-oxide flooring, in almost every old Bangalore home — primary accent |
| `verdigris` | `#4B6B58` | Bronze patina on temple bells/idols — cool complementary accent |
| `turmeric` | `#C68A2E` | Market spice / gopuram polychrome — sparing highlight |
| `sandstone` | `#C7B79C` | Muted clay — borders/dividers |

Red Oxide and Verdigris sit roughly complementary on the color wheel
(warm red vs. cool green), which is what gives buttons/links/status states
real contrast without reaching for blue. Turmeric is analogous to Red Oxide
and stays reserved for small highlights so it doesn't compete with the
primary accent.

Type: **Fraunces** (display), **Work Sans** (body), **Space Mono** (data —
prices, durations, distances).

**Signature element:** tours are shown as **ticket stubs** — perforated
edge, rubber-stamp status badge (UNBOOKED / BOOKED / WALKING / COMPLETED).
It's a distinctly Bangalore reference (BMTC bus tickets) that also mirrors
the product's real rule: a tour license is used once, like a ticket
punched once.

## Setup

```bash
npm install
cp .env.example .env.local   # point VITE_API_BASE_URL at your backend
npm run dev
```

Needs the backend running and seeded first (see `../backend/README.md`).

## What's implemented

- Auth (signup/login/logout), session persisted in localStorage
- Home feed with the tour catalog
- Tour detail: status-aware CTA (buy → start → continue → completed),
  likes, comments (gated on completed walk, same as backend/mobile)
- Walk experience: browser Geolocation `watchPosition`, HTML5 `<audio>`
  playback triggered on entering a stop's radius, events queued in
  `localStorage` first and synced opportunistically (`client_event_id`
  makes resend safe) — same offline-first pattern as the mobile app,
  adapted for the browser
- Walk complete + profile pages

## Known gaps

- No offline file caching (Service Worker / Cache API) — audio streams
  live rather than being downloaded up front, unlike the mobile app.
  Worth adding if this needs to work in real dead zones.
- No refresh-token rotation on 401 yet.
- Manual "mark visited" buttons are a fallback for desktop testing where
  GPS doesn't move — remove or hide behind a dev flag before shipping.
