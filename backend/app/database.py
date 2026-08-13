from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


# Async engine — used by FastAPI at runtime.
# echo=settings.DEBUG ensures SQL queries (including those touching password
# hashes and JWTs) are never logged in production unless DEBUG=True is set.
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
    )
else:
    engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=settings.DEBUG,
    )

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


# Base class — all SQLAlchemy models inherit from this
class Base(DeclarativeBase):
    pass


# Dependency — used in FastAPI routes via Depends(get_db)
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise