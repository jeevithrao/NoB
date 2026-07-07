-- ============================================================
-- Ethnography Audio Tour App — PostgreSQL Schema
-- Run this once on a fresh database:
--   psql -U postgres -d ethnography_db -f schema.sql
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- uuid_generate_v4()
CREATE EXTENSION IF NOT EXISTS "pgcrypto";    -- gen_random_uuid() (Postgres 13+ alternative)

-- ============================================================
-- 1. USERS
-- role: 'user' | 'admin'
-- ============================================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    full_name       VARCHAR(255),
    role            VARCHAR(20) NOT NULL DEFAULT 'user'
                        CHECK (role IN ('user', 'admin')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 2. TOURS
-- price_paise: store money as integer paise (₹1 = 100 paise)
--              avoids all floating-point money bugs
-- is_free: true  → skip payment gate entirely
--          false → check purchases table before allowing download
-- ============================================================
CREATE TABLE tours (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    city            VARCHAR(100) NOT NULL,
    cover_image     VARCHAR(500),          -- filename, served via Nginx
    duration_min    INTEGER,               -- estimated walk duration
    distance_km     NUMERIC(5, 2),         -- e.g. 2.40
    price_paise     INTEGER NOT NULL DEFAULT 0
                        CHECK (price_paise >= 0),
    is_free         BOOLEAN NOT NULL DEFAULT FALSE,
    is_published    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 3. STOPS
-- lat/lng: NUMERIC(10,7) gives ~1cm precision — sufficient for GPS
-- trigger_radius_m: proximity in metres to fire audio (default 30m)
-- order_index: 1-based ordering within a tour
-- ============================================================
CREATE TABLE stops (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tour_id             UUID NOT NULL REFERENCES tours(id) ON DELETE CASCADE,
    order_index         INTEGER NOT NULL,
    name                VARCHAR(255) NOT NULL,
    narrative_text      TEXT,              -- shown in the "arrived" card
    lat                 NUMERIC(10, 7) NOT NULL,
    lng                 NUMERIC(10, 7) NOT NULL,
    trigger_radius_m    INTEGER NOT NULL DEFAULT 30
                            CHECK (trigger_radius_m > 0),
    audio_filename      VARCHAR(500) NOT NULL,   -- e.g. "pete_lane_stop_1.mp3"
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (tour_id, order_index)          -- no duplicate positions in a tour
);

-- ============================================================
-- 4. PURCHASES
-- status: 'pending'   → order created, payment not confirmed yet
--         'completed' → webhook confirmed, tour unlocked
--         'failed'    → payment failed or refunded
-- amount_paise: snapshot of price at time of purchase
-- ============================================================
CREATE TABLE purchases (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tour_id                 UUID NOT NULL REFERENCES tours(id) ON DELETE CASCADE,
    gateway_order_id        VARCHAR(255) UNIQUE,    -- Razorpay/Stripe order id
    gateway_payment_id      VARCHAR(255) UNIQUE,    -- Razorpay/Stripe payment id
    amount_paise            INTEGER NOT NULL,
    status                  VARCHAR(20) NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending', 'completed', 'failed')),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (user_id, tour_id)             -- one purchase record per user-tour pair
                                          -- status field tracks state changes
);

-- ============================================================
-- 5. TOUR_SESSIONS
-- One row per user per tour walk attempt.
-- stops_visited: incremented each time a stop audio fires.
-- ============================================================
CREATE TABLE tour_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tour_id         UUID NOT NULL REFERENCES tours(id) ON DELETE CASCADE,
    stops_visited   INTEGER NOT NULL DEFAULT 0,
    completed       BOOLEAN NOT NULL DEFAULT FALSE,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

-- ============================================================
-- 6. SESSION_EVENTS  (analytics / granular stop tracking)
-- event_type: 'arrived' | 'audio_started' | 'audio_finished' | 'skipped'
-- Kept separate from tour_sessions to allow multiple events per stop.
-- ============================================================
CREATE TABLE session_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID NOT NULL REFERENCES tour_sessions(id) ON DELETE CASCADE,
    stop_id         UUID NOT NULL REFERENCES stops(id) ON DELETE CASCADE,
    event_type      VARCHAR(30) NOT NULL
                        CHECK (event_type IN ('arrived','audio_started','audio_finished','skipped')),
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 7. SAVED_TOURS  (user bookmarks / wishlist)
-- Composite PK — a user can only save a tour once.
-- ============================================================
CREATE TABLE saved_tours (
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tour_id         UUID NOT NULL REFERENCES tours(id) ON DELETE CASCADE,
    saved_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (user_id, tour_id)
);

-- ============================================================
-- INDEXES
-- Only on columns actually used in WHERE / JOIN / ORDER BY.
-- ============================================================

-- Tours: list published tours by city
CREATE INDEX idx_tours_city          ON tours(city);
CREATE INDEX idx_tours_is_published  ON tours(is_published);

-- Stops: fetch all stops for a tour in order (most common query)
CREATE INDEX idx_stops_tour_order    ON stops(tour_id, order_index);

-- Purchases: access check (user_id + tour_id + status='completed')
CREATE INDEX idx_purchases_user_tour ON purchases(user_id, tour_id);
CREATE INDEX idx_purchases_gateway   ON purchases(gateway_order_id);

-- Sessions: look up active session for a user+tour
CREATE INDEX idx_sessions_user_tour  ON tour_sessions(user_id, tour_id);

-- Events: analytics queries by session
CREATE INDEX idx_events_session      ON session_events(session_id);

-- ============================================================
-- AUTO-UPDATE updated_at TRIGGER
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_tours_updated_at
    BEFORE UPDATE ON tours
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_purchases_updated_at
    BEFORE UPDATE ON purchases
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- SEED: one admin user for testing
-- Password is 'admin123' — CHANGE THIS before any real deployment
-- Hash generated with bcrypt (12 rounds) — replace with real hash
-- ============================================================
INSERT INTO users (email, password_hash, full_name, role)
VALUES (
    'admin@ethnowalk.com',
    '$2b$12$PLACEHOLDER_REPLACE_WITH_REAL_BCRYPT_HASH',
    'App Admin',
    'admin'
);

