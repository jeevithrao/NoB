-- ============================================================
-- NoB — Neighbourhoods of Bengaluru
-- PostgreSQL Schema v2 — Updated per PRD v1
--
-- Changes from v1:
--   + device_id added to purchases (device binding)
--   + is_locked added to purchases (one-lifetime-use)
--   + user_login_sessions table (single active session)
--   + tour_likes table (likes on completed tours)
--   + tour_comments table (comments on completed tours)
--   + New indexes for all new tables/columns
--
-- Run on a fresh database:
--   psql -U ethnowalk_user -d "NoB_db" -f Nob_schema.sql
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- 1. USERS
-- role: 'user' | 'admin'
-- ============================================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    full_name       VARCHAR(255),
    avatar_url      VARCHAR(500),
    role            VARCHAR(20) NOT NULL DEFAULT 'user'
                        CHECK (role IN ('user', 'admin')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 2. USER_LOGIN_SESSIONS  [NEW — Gap 3]
-- Tracks active login sessions per user.
-- Only ONE row per user can have is_active = TRUE at a time.
-- When user logs in on a new device, all previous rows for
-- that user are set to is_active = FALSE (kicked out).
-- This enforces the "single active session" rule from the PRD.
-- ============================================================
CREATE TABLE user_login_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id       VARCHAR(255) NOT NULL,   -- unique identifier for the device
    refresh_token   TEXT NOT NULL UNIQUE,    -- the refresh token issued at login
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,    -- refresh token expiry
    last_used_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 3. TOURS
-- price_paise: store money as integer paise (₹1 = 100 paise)
-- is_free: skip payment gate entirely if TRUE
-- is_published: drafts never visible in the mobile app
-- ============================================================
CREATE TABLE tours (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    city            VARCHAR(100) NOT NULL,
    cover_image     VARCHAR(500),
    duration_min    INTEGER,
    distance_km     NUMERIC(5, 2),
    price_paise     INTEGER NOT NULL DEFAULT 0
                        CHECK (price_paise >= 0),
    is_free         BOOLEAN NOT NULL DEFAULT FALSE,
    is_published    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 4. STOPS
-- lat/lng: NUMERIC(10,7) gives ~1cm GPS precision
-- trigger_radius_m: geofence radius to fire audio (default 30m)
-- order_index: 1-based position within the tour
-- ============================================================
CREATE TABLE stops (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tour_id             UUID NOT NULL REFERENCES tours(id) ON DELETE CASCADE,
    order_index         INTEGER NOT NULL,
    name                VARCHAR(255) NOT NULL,
    narrative_text      TEXT,
    lat                 NUMERIC(10, 7) NOT NULL,
    lng                 NUMERIC(10, 7) NOT NULL,
    trigger_radius_m    INTEGER NOT NULL DEFAULT 30
                            CHECK (trigger_radius_m > 0),
    audio_filename      VARCHAR(500) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (tour_id, order_index)
);

-- ============================================================
-- 5. PURCHASES
-- status:    'pending'   → order created, not yet paid
--            'completed' → webhook confirmed, tour unlocked
--            'failed'    → payment failed or refunded
--
-- device_id: [NEW — Gap 1] the device that first downloaded
--            this tour. A second device triggers re-download
--            which is gated by single-session login.
--
-- is_locked: [NEW — Gap 2] flips to TRUE when
--            tour_sessions.completed = TRUE for this purchase.
--            Once locked, the user cannot start a new walk
--            without repurchasing (one-lifetime-use rule).
--
-- amount_paise: snapshot of price at time of purchase.
-- ============================================================
CREATE TABLE purchases (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tour_id                 UUID NOT NULL REFERENCES tours(id) ON DELETE CASCADE,
    gateway_order_id        VARCHAR(255) UNIQUE,
    gateway_payment_id      VARCHAR(255) UNIQUE,
    amount_paise            INTEGER NOT NULL,
    status                  VARCHAR(20) NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending', 'completed', 'failed')),
    device_id               VARCHAR(255),        -- [NEW] bound device
    is_locked               BOOLEAN NOT NULL DEFAULT FALSE,  -- [NEW] one-lifetime-use
    locked_at               TIMESTAMPTZ,         -- [NEW] when it was locked
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (user_id, tour_id)
);

-- ============================================================
-- 6. TOUR_SESSIONS
-- One row per walk attempt.
-- completed: flips TRUE on final stop → triggers purchase lock.
-- is_resumable: TRUE while walk is in progress but not done.
--   Interrupted walks are resumable and do NOT consume
--   the license (per PRD business rules).
-- ============================================================
CREATE TABLE tour_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tour_id         UUID NOT NULL REFERENCES tours(id) ON DELETE CASCADE,
    purchase_id     UUID REFERENCES purchases(id) ON DELETE SET NULL,
    stops_visited   INTEGER NOT NULL DEFAULT 0,
    completed       BOOLEAN NOT NULL DEFAULT FALSE,
    is_resumable    BOOLEAN NOT NULL DEFAULT TRUE,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

-- ============================================================
-- 7. SESSION_EVENTS
-- Granular analytics per stop action.
-- event_type: 'arrived' | 'audio_started' |
--             'audio_finished' | 'skipped'
-- ============================================================
CREATE TABLE session_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID NOT NULL REFERENCES tour_sessions(id) ON DELETE CASCADE,
    stop_id         UUID NOT NULL REFERENCES stops(id) ON DELETE CASCADE,
    event_type      VARCHAR(30) NOT NULL
                        CHECK (event_type IN (
                            'arrived',
                            'audio_started',
                            'audio_finished',
                            'skipped'
                        )),
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 8. SAVED_TOURS
-- User bookmarks / wishlist.
-- Composite PK: a user can only save a tour once.
-- ============================================================
CREATE TABLE saved_tours (
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tour_id         UUID NOT NULL REFERENCES tours(id) ON DELETE CASCADE,
    saved_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (user_id, tour_id)
);

-- ============================================================
-- 9. TOUR_LIKES  [NEW — Gap 4]
-- Users can like a tour only after completing it.
-- This is enforced in the backend (check tour_sessions.completed).
-- Composite PK: a user can only like a tour once.
-- ============================================================
CREATE TABLE tour_likes (
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tour_id         UUID NOT NULL REFERENCES tours(id) ON DELETE CASCADE,
    liked_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (user_id, tour_id)
);

-- ============================================================
-- 10. TOUR_COMMENTS  [NEW — Gap 4]
-- Users can comment on a tour only after completing it.
-- is_deleted: soft delete — content hidden but row kept
--             for moderation audit trail.
-- ============================================================
CREATE TABLE tour_comments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tour_id         UUID NOT NULL REFERENCES tours(id) ON DELETE CASCADE,
    content         TEXT NOT NULL
                        CHECK (char_length(content) BETWEEN 1 AND 1000),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,  -- soft delete
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- INDEXES
-- ============================================================

-- Users
-- (email already has UNIQUE index)

-- Login sessions: fast lookup of active session by user
CREATE INDEX idx_login_sessions_user_id    ON user_login_sessions(user_id);
CREATE INDEX idx_login_sessions_device     ON user_login_sessions(device_id);
CREATE INDEX idx_login_sessions_active     ON user_login_sessions(user_id, is_active);

-- Tours
CREATE INDEX idx_tours_city               ON tours(city);
CREATE INDEX idx_tours_is_published       ON tours(is_published);

-- Stops: fetch all stops for a tour in order (most frequent query)
CREATE INDEX idx_stops_tour_order         ON stops(tour_id, order_index);

-- Purchases: access check + device check
CREATE INDEX idx_purchases_user_tour      ON purchases(user_id, tour_id);
CREATE INDEX idx_purchases_gateway        ON purchases(gateway_order_id);
CREATE INDEX idx_purchases_device         ON purchases(device_id);       -- [NEW]
CREATE INDEX idx_purchases_is_locked      ON purchases(is_locked);       -- [NEW]

-- Sessions
CREATE INDEX idx_sessions_user_tour       ON tour_sessions(user_id, tour_id);
CREATE INDEX idx_sessions_purchase        ON tour_sessions(purchase_id); -- [NEW]

-- Session events
CREATE INDEX idx_events_session           ON session_events(session_id);

-- Likes: count likes per tour quickly
CREATE INDEX idx_likes_tour_id            ON tour_likes(tour_id);        -- [NEW]

-- Comments: fetch comments for a tour, newest first
CREATE INDEX idx_comments_tour_id         ON tour_comments(tour_id);     -- [NEW]
CREATE INDEX idx_comments_user_id         ON tour_comments(user_id);     -- [NEW]

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

CREATE TRIGGER trg_comments_updated_at
    BEFORE UPDATE ON tour_comments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- TOUR LOCK TRIGGER  [NEW — Gap 2]
-- When tour_sessions.completed flips to TRUE,
-- automatically lock the corresponding purchase
-- by setting purchases.is_locked = TRUE and locked_at = NOW().
-- This enforces one-lifetime-use at the database level,
-- not just in application code.
-- ============================================================
CREATE OR REPLACE FUNCTION lock_purchase_on_completion()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.completed = TRUE AND OLD.completed = FALSE THEN
        UPDATE purchases
        SET
            is_locked  = TRUE,
            locked_at  = NOW(),
            updated_at = NOW()
        WHERE
            id = NEW.purchase_id
            AND is_locked = FALSE;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_lock_purchase_on_session_complete
    AFTER UPDATE ON tour_sessions
    FOR EACH ROW EXECUTE FUNCTION lock_purchase_on_completion();

-- ============================================================
-- SINGLE SESSION ENFORCEMENT  [NEW — Gap 3]
-- When a new user_login_sessions row is inserted,
-- automatically deactivate all other active sessions
-- for that user (kicks out old device).
-- ============================================================
CREATE OR REPLACE FUNCTION deactivate_old_sessions()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE user_login_sessions
    SET is_active = FALSE
    WHERE
        user_id   = NEW.user_id
        AND id    != NEW.id
        AND is_active = TRUE;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_single_active_session
    AFTER INSERT ON user_login_sessions
    FOR EACH ROW EXECUTE FUNCTION deactivate_old_sessions();

