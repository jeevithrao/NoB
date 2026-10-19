"""Direct-to-database builders for test data (bypass the API on purpose)."""
import uuid
from decimal import Decimal

from app.core.security import hash_password
from app.models import Neighbourhood, Stop, Tour, User
from tests.helpers import login, new_device, new_email


async def make_neighbourhood(client, name: str = "Malleshwaram") -> Neighbourhood:
    async with client.session_factory() as db:
        hood = Neighbourhood(name=name, slug=name.lower().replace(" ", "-") + "-" + uuid.uuid4().hex[:4])
        db.add(hood)
        await db.commit()
        await db.refresh(hood)
        return hood


async def make_tour(
    client,
    *,
    name: str | None = None,
    price_paise: int = 19900,
    is_free: bool = False,
    published: bool = True,
    stops: int = 3,
    neighbourhood_id: uuid.UUID | None = None,
) -> dict:
    async with client.session_factory() as db:
        tour = Tour(
            name=name or f"Tour {uuid.uuid4().hex[:6]}",
            description="A test walk.",
            city="Bangalore",
            duration_min=45,
            distance_km=Decimal("2.0"),
            price_paise=0 if is_free else price_paise,
            is_free=is_free,
            is_published=published,
            neighbourhood_id=neighbourhood_id,
        )
        db.add(tour)
        await db.flush()
        stop_ids = []
        for i in range(1, stops + 1):
            stop = Stop(
                tour_id=tour.id,
                order_index=i,
                name=f"Stop {i}",
                narrative_text=f"Narration {i}",
                lat=Decimal("13.0035") + Decimal(i) / 10000,
                lng=Decimal("77.5647"),
                trigger_radius_m=30,
                audio_filename=f"test/{i:02d}.mp3",
            )
            db.add(stop)
            await db.flush()
            stop_ids.append(stop.id)
        await db.commit()
        return {"id": tour.id, "stop_ids": stop_ids, "price_paise": tour.price_paise}


async def make_admin(client, password: str = "admin-pass-12345") -> dict:
    """Create an admin directly in the DB and log in through the API."""
    email, device = new_email("admin"), new_device()
    async with client.session_factory() as db:
        db.add(User(email=email, password_hash=hash_password(password), role="admin"))
        await db.commit()
    resp = await login(client, email, password, device)
    assert resp.status_code == 200, resp.text
    return {"email": email, "device": device, **resp.json()}
