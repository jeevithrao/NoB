"""Seeds a couple of demo tours so the app is browsable/purchasable/walkable
right away. Run with:  python -m app.seed
Safe to re-run — skips creation if the admin user / tours already exist.
"""

import asyncio
import copy

from app.core.security import hash_password
from app.database import AsyncSessionLocal
from app.models import Stop, Tour, User
from app.seed_data import TOURS
from sqlalchemy import select


ADMIN_EMAIL = "admin@nob.app"
ADMIN_PASSWORD = "AdminPass123!"



async def seed() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == ADMIN_EMAIL))
        admin = result.scalar_one_or_none()
        if admin is None:
            admin = User(
                email=ADMIN_EMAIL,
                password_hash=hash_password(ADMIN_PASSWORD),
                full_name="NoB Admin",
                role="admin",
            )
            db.add(admin)
            print(f"Created admin user: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        else:
            print(f"Admin user already exists: {ADMIN_EMAIL}")

        for tour_data in TOURS:
            result = await db.execute(select(Tour).where(Tour.name == tour_data["name"]))
            if result.scalar_one_or_none() is not None:
                print(f"Tour already exists, skipping: {tour_data['name']}")
                continue

            tour_data = copy.deepcopy(tour_data)
            stops_data = tour_data.pop("stops")
            tour = Tour(**tour_data, is_published=True)
            db.add(tour)
            await db.flush()

            for i, stop_data in enumerate(stops_data, start=1):
                db.add(Stop(tour_id=tour.id, order_index=i, **stop_data))

            print(f"Created tour: {tour.name} ({len(stops_data)} stops)")

        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
