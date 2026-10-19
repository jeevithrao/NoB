# System Architecture / Technical Design Document — v1

## High-level architecture

```
┌─────────────────────┐        HTTPS/REST        ┌──────────────────────┐
│  React Native App    │◀────────────────────────▶│   Backend API         │
│  (iOS + Android)      │                          │   (Python / FastAPI)  │
└─────────┬────────────┘                          └──────────┬───────────┘
          │                                                    │
          │ Local storage:                                    │
          │ - Downloaded audio                                 │
          │ - Stop/route manifest                              │
          │ - Queued session events (offline)                  │
          │                                                    │
          ▼                                                    ▼
┌──────────────────────┐                         ┌──────────────────────┐
│ Maps/Geolocation SDK  │                         │ PostgreSQL            │
│ (Mapbox/Google Maps)  │                         │ (schema + extensions) │
└──────────────────────┘                         └──────────┬───────────┘
                                                              │
                                                              ▼
                                                   ┌──────────────────────┐
                                                   │ Object Storage (S3)   │
                                                   │ - Audio files          │
                                                   │ - Cover images         │
                                                   └──────────────────────┘

Backend also integrates:
- Payment gateway (Razorpay/Stripe) — order creation + webhook receiver
- SMS/Email provider — OTP delivery
```

## Components

**Mobile app (React Native)**
- Handles all offline-first logic: once a tour is downloaded, the walk itself needs zero backend calls.
- Local storage layer (e.g. SQLite or file system + AsyncStorage) for downloaded manifests, audio, and a queue of unsynced session events.
- Background sync job: on app foreground + network available, flush queued events to `/sessions/{id}/events/batch`.

**Backend API (Python/FastAPI recommended)**
- Stateless REST API, JWT auth.
- Responsible for: auth/session management, tour catalog, purchase orchestration, signed-URL generation for audio, session/event ingestion, admin operations.
- Webhook receiver for payment gateway confirmations — must be idempotent and signature-verified.

**Database (PostgreSQL)**
- Source of truth for users, tours, stops, purchases, sessions, devices, auth sessions, neighbourhoods, likes/comments (schema already drafted across the two schema files).

**Object storage (S3-compatible)**
- Stores raw audio files and cover images. Backend generates time-limited signed URLs; it never proxies large files itself.

**Admin tooling**
- v1 can be minimal: either a basic internal web dashboard or even direct-to-database scripts/admin endpoints callable via a simple internal tool — full-featured CMS is a later investment, not a v1 blocker.

## Key architectural decisions (ADR-style, brief)

1. **Offline-first is a hard requirement, not a nice-to-have** — this shapes the mobile app's local storage and sync design far more than typical CRUD apps; plan the local data layer before writing UI screens.
2. **Licensing enforcement lives in the database + API, not just the client** — `tour_sessions.completed` and `purchases.bound_device_id` are server-side source of truth; the app must always defer to server state on login/download, never trust local-only flags for "do I own this."
3. **No real-time backend needed** — nothing here requires websockets/live multiplayer; simple REST + polling/webhooks is sufficient for v1.
4. **Payment data never touches our servers directly** — gateway SDK/hosted checkout only; reduces PCI compliance burden significantly.

## Environments
- Recommend three environments minimum: `dev`, `staging`, `production` — separate databases and object storage buckets per environment, separate payment gateway test/live keys.

## Open technical decisions for the dev team to make (not pre-decided here)
- Exact hosting provider for backend + Postgres (e.g. Render/Railway/AWS — team's call based on cost/familiarity).
- Local mobile storage mechanism (SQLite vs. file-system-based) — implementation detail, not product-level.
- Exact push notification provider, if/when that's added post-v1.
