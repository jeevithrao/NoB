-- ============================================================
-- DESIGN REFERENCE ONLY — the live schema is built by Alembic
-- (backend/alembic/versions). Do not run this file by hand.
-- See docs/DATABASE.md for how this design maps to the real tables.
-- ============================================================
-- Neighbourhoods of Bangalore — Schema Extensions
-- Run AFTER the existing Nob_schema.sql
-- Adds: device binding, single-session enforcement, neighbourhoods,
--       lightweight comments/likes
-- ============================================================

-- ============================================================
-- 8. DEVICES
-- One row per app install. device_identifier is a UUID generated
-- client-side on first launch and persisted (not a hardware serial).
-- ============================================================
CREATE TABLE devices (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_identifier   VARCHAR(255) NOT NULL UNIQUE,
    device_name         VARCHAR(255),          -- e.g. "iPhone 14" for user-facing device list
    first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_devices_user ON devices(user_id);

-- ============================================================
-- 9. AUTH_SESSIONS
-- Enforces single active login session per account.
-- On new login: invalidate any other row for that user_id (is_active = FALSE).
-- ============================================================
CREATE TABLE auth_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id       UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    token_hash      TEXT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_auth_sessions_user_active ON auth_sessions(user_id, is_active);

-- ============================================================
-- ALTER: purchases — bind a purchase to the device that first
-- downloaded it for offline use. NULL until first download.
-- ============================================================
ALTER TABLE purchases
    ADD COLUMN bound_device_id UUID REFERENCES devices(id);

-- ============================================================
-- ALTER: tour_sessions — completed = TRUE is the "consumed" flag.
-- (Already exists — no schema change needed, documented here for clarity.)
-- Business rule: once completed = TRUE, no new session may be created
-- for that (user_id, tour_id) pair. Enforce in application logic,
-- or optionally via a partial unique index:
-- ============================================================
CREATE UNIQUE INDEX idx_one_completed_session_per_user_tour
    ON tour_sessions(user_id, tour_id)
    WHERE completed = TRUE;
-- This still allows multiple non-completed (in-progress/abandoned) rows
-- historically, but guarantees only one completed row ever exists —
-- the application should look up the existing in-progress row and
-- resume it rather than creating a new one each time.

-- ============================================================
-- 10. NEIGHBOURHOODS
-- Groups tours by area (Indiranagar, Malleshwaram, etc.)
-- ============================================================
CREATE TABLE neighbourhoods (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(255) NOT NULL,
    city            VARCHAR(100) NOT NULL DEFAULT 'Bangalore',
    description     TEXT,
    cover_image     VARCHAR(500),
    centroid_lat    NUMERIC(10, 7),        -- for placing the pin on the illustrated map
    centroid_lng    NUMERIC(10, 7),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (name, city)
);

ALTER TABLE tours
    ADD COLUMN neighbourhood_id UUID REFERENCES neighbourhoods(id);

CREATE INDEX idx_tours_neighbourhood ON tours(neighbourhood_id);

-- ============================================================
-- 11. TOUR_LIKES  (lightweight reaction, not a social feed)
-- ============================================================
CREATE TABLE tour_likes (
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tour_id         UUID NOT NULL REFERENCES tours(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (user_id, tour_id)
);

-- ============================================================
-- 12. TOUR_COMMENTS
-- Only purchasers who have completed the tour may comment —
-- enforce in application logic (check tour_sessions.completed = TRUE).
-- ============================================================
CREATE TABLE tour_comments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tour_id         UUID NOT NULL REFERENCES tours(id) ON DELETE CASCADE,
    comment_text    TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tour_comments_tour ON tour_comments(tour_id, created_at);
