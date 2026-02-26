from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from src.infrastructure.db.models import DiningTableSlot, Event, EventSeatType
from src.infrastructure.db.session import SessionLocal


def _dt(days_from_now: int, hour: int, minute: int) -> datetime:
    ist = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist)
    target = now_ist + timedelta(days=days_from_now)
    return target.replace(hour=hour, minute=minute, second=0, microsecond=0)


def seed_events(db) -> None:
    event_defs = [
        {
            "title": "Sunidhi Chauhan Live Concert",
            "type": "CONCERT",
            "date_time": _dt(days_from_now=10, hour=19, minute=30),
            "location": "Indira Gandhi Arena, New Delhi",
            "seat_types": [
                {"seat_type": "Regular", "price": 1800, "total_seats": 400},
                {"seat_type": "VIP", "price": 4500, "total_seats": 120},
            ],
        },
        {
            "title": "Holi Festival 2026",
            "type": "FESTIVAL",
            "date_time": _dt(days_from_now=15, hour=11, minute=0),
            "location": "Jawaharlal Nehru Stadium Grounds, Delhi",
            "seat_types": [
                {"seat_type": "General", "price": 1200, "total_seats": 700},
                {"seat_type": "Premium", "price": 2800, "total_seats": 180},
            ],
        },
    ]

    for item in event_defs:
        existing = db.execute(
            select(Event).where(Event.title == item["title"])
        ).scalar_one_or_none()
        if existing:
            db.execute(delete(EventSeatType).where(EventSeatType.event_id == existing.id))
            event = existing
            event.type = item["type"]
            event.date_time = item["date_time"]
            event.location = item["location"]
        else:
            event = Event(
                title=item["title"],
                type=item["type"],
                date_time=item["date_time"],
                location=item["location"],
            )
            db.add(event)
            db.flush()

        for seat in item["seat_types"]:
            db.add(
                EventSeatType(
                    event_id=event.id,
                    seat_type=seat["seat_type"],
                    price=seat["price"],
                    total_seats=seat["total_seats"],
                    available_seats=seat["total_seats"],
                )
            )


def seed_dining(db) -> None:
    slots = [
        {
            "restaurant_name": "Hotel Star",
            "table_number": "A1",
            "capacity": 2,
            "price_per_table": 1500,
            "date_time": _dt(days_from_now=2, hour=20, minute=0),
        },
        {
            "restaurant_name": "Hotel Star",
            "table_number": "B4",
            "capacity": 4,
            "price_per_table": 2800,
            "date_time": _dt(days_from_now=2, hour=21, minute=30),
        },
        {
            "restaurant_name": "Hotel Star",
            "table_number": "C2",
            "capacity": 6,
            "price_per_table": 4200,
            "date_time": _dt(days_from_now=3, hour=20, minute=15),
        },
    ]

    for slot in slots:
        existing = db.execute(
            select(DiningTableSlot)
            .where(DiningTableSlot.restaurant_name == slot["restaurant_name"])
            .where(DiningTableSlot.table_number == slot["table_number"])
            .where(DiningTableSlot.date_time == slot["date_time"])
        ).scalar_one_or_none()
        if existing:
            existing.capacity = slot["capacity"]
            existing.price_per_table = slot["price_per_table"]
            existing.status = "AVAILABLE"
            continue

        db.add(
            DiningTableSlot(
                restaurant_name=slot["restaurant_name"],
                table_number=slot["table_number"],
                capacity=slot["capacity"],
                price_per_table=slot["price_per_table"],
                date_time=slot["date_time"],
                status="AVAILABLE",
            )
        )


def main() -> None:
    db = SessionLocal()
    try:
        seed_events(db)
        seed_dining(db)
        db.commit()
        print("Seed complete: Sunidhi concert, Holi festival, Hotel Star dining slots added.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
