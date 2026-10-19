"""Test harness.

Runs the real FastAPI app against a real PostgreSQL database (never SQLite:
the licensing rules rely on Postgres partial indexes and UUID types).

Configure with:
  TEST_DATABASE_URL       postgresql+asyncpg://user:pw@host:5432/nob_test
  TEST_DATABASE_URL_SYNC  postgresql://user:pw@host:5432/nob_test
The target database is wiped on every run — point it at a throw-away DB.
"""
import os

# --- Settings must be in the environment BEFORE `app` is imported ------------
_ASYNC_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://nob_user:nob_pass@localhost:5432/nob_test"
)
_SYNC_URL = os.environ.get(
    "TEST_DATABASE_URL_SYNC", "postgresql://nob_user:nob_pass@localhost:5432/nob_test"
)
os.environ.update(
    {
        "ENVIRONMENT": "development",
        "DATABASE_URL": _ASYNC_URL,
        "DATABASE_URL_SYNC": _SYNC_URL,
        "SECRET_KEY": "test-secret-key-for-the-test-suite-only-0123456789",
        "EMAIL_BACKEND": "memory",
        "EXPOSE_DEV_OTP": "false",
        "MOCK_PAYMENTS": "true",
        "DEBUG": "false",
        "RATE_LIMIT_AUTH_PER_MINUTE": "1000",
    }
)

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.core.rate_limit import limiter  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app import models as _models  # noqa: E402,F401  (register every model on Base.metadata)
from app.services.email import MemoryBackend, set_email_backend  # noqa: E402


BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session")
def sync_engine():
    """Fresh database built by the real Alembic migrations (not create_all), so
    the tests exercise exactly the schema production gets."""
    from alembic import command
    from alembic.config import Config

    engine = create_engine(_SYNC_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    command.upgrade(cfg, "head")
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_state(sync_engine):
    """Empty every table and reset in-process state before each test."""
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)  # alembic_version is kept
    with sync_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    limiter.reset()
    set_email_backend(MemoryBackend())
    yield
    set_email_backend(None)


@pytest_asyncio.fixture
async def db_engine():
    # NullPool: each test has its own event loop, so no connection may outlive it.
    engine = create_async_engine(_ASYNC_URL, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        c.session_factory = factory  # handy for tests that need direct DB access
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def outbox():
    """Messages 'sent' by the in-memory email backend."""
    from app.services import email as email_service

    return email_service.get_email_backend().outbox


@pytest.fixture
def razorpay(monkeypatch):
    """Real-payments mode with a fake Razorpay behind it."""
    import httpx

    from app.config import settings
    from app.services import payments
    from tests.payments_helpers import KEY_ID, KEY_SECRET, WEBHOOK_SECRET, FakeRazorpay

    monkeypatch.setattr(settings, "MOCK_PAYMENTS", False)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", KEY_ID)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", KEY_SECRET)
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", WEBHOOK_SECRET)
    fake = FakeRazorpay()
    payments.set_transport(httpx.MockTransport(fake.handler))
    yield fake
    payments.set_transport(None)
