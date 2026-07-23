import asyncio
import sys
import os

from sqlalchemy.ext.asyncio import create_async_engine
from app.database import Base
from app.models import (
    User,
    UserLoginSession,
    Tour,
    Stop,
    Purchase,
    TourSession,
    SessionEvent,
    SavedTour,
    TourLike,
    TourComment
)

async def main():
    database_url = "sqlite+aiosqlite:///./nob.db"
    print(f"Initializing SQLite database at {database_url}...")
    engine = create_async_engine(database_url, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables initialized successfully!")

if __name__ == "__main__":
    asyncio.run(main())
