"""Schema-level guarantees. The licensing model is enforced in the database as
well as in the API, so a bug or a race in application code cannot break it."""
import uuid

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.database import Base

EXPECTED_TABLES = {
    "users", "user_login_sessions", "otp_requests", "neighbourhoods", "tours", "stops",
    "purchases", "tour_sessions", "session_events", "saved_tours", "tour_likes", "tour_comments",
}


def test_migrations_create_every_table(sync_engine):
    assert EXPECTED_TABLES <= set(inspect(sync_engine).get_table_names())


def test_models_and_migrations_have_not_drifted(sync_engine):
    """Fails if someone changes a model without writing a migration."""
    with sync_engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


@pytest.fixture
def world(sync_engine):
    """A user and a paid tour inserted with raw SQL (no API involved)."""
    ids = {k: uuid.uuid4() for k in ("user", "tour", "purchase")}
    with sync_engine.begin() as c:
        c.execute(text("INSERT INTO users (id, email, password_hash, role) VALUES (:u, :e, 'x', 'user')"),
                  {"u": ids["user"], "e": f"{ids['user']}@nobtests.com"})
        c.execute(text("INSERT INTO tours (id, name, city, price_paise, is_free, is_published) "
                       "VALUES (:t, 'T', 'Bangalore', 9900, false, true)"), {"t": ids["tour"]})
    return ids


def _session(c, w, completed):
    c.execute(text("INSERT INTO tour_sessions (id, user_id, tour_id, completed, stops_visited, is_resumable) "
                   "VALUES (:i, :u, :t, :c, 0, true)"),
              {"i": uuid.uuid4(), "u": w["user"], "t": w["tour"], "c": completed})


def test_only_one_completed_session_per_user_and_tour(sync_engine, world):
    with sync_engine.begin() as c:
        _session(c, world, True)
    with pytest.raises(IntegrityError):
        with sync_engine.begin() as c:
            _session(c, world, True)


def test_many_unfinished_sessions_are_allowed(sync_engine, world):
    with sync_engine.begin() as c:
        _session(c, world, False)
        _session(c, world, False)
        _session(c, world, True)


def _purchase(c, w, status, **extra):
    c.execute(text("INSERT INTO purchases (id, user_id, tour_id, amount_paise, status, is_locked) "
                   "VALUES (:i, :u, :t, 9900, :s, false)"),
              {"i": uuid.uuid4(), "u": w["user"], "t": w["tour"], "s": status})


def test_one_active_purchase_per_user_and_tour(sync_engine, world):
    with sync_engine.begin() as c:
        _purchase(c, world, "completed")
    with pytest.raises(IntegrityError):
        with sync_engine.begin() as c:
            _purchase(c, world, "pending")


def test_failed_and_refunded_purchases_do_not_block_a_rebuy(sync_engine, world):
    with sync_engine.begin() as c:
        _purchase(c, world, "failed")
        _purchase(c, world, "refunded")
        _purchase(c, world, "completed")


def test_invalid_purchase_status_is_rejected(sync_engine, world):
    with pytest.raises(IntegrityError):
        with sync_engine.begin() as c:
            _purchase(c, world, "bogus")


@pytest.mark.parametrize("sql", [
    "UPDATE users SET role = 'superuser'",
    "UPDATE tours SET price_paise = -1",
])
def test_check_constraints_reject_bad_values(sync_engine, world, sql):
    with pytest.raises(IntegrityError):
        with sync_engine.begin() as c:
            c.execute(text(sql))
