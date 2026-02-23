# src/infrastructure/repositories/seat_repository.py

from sqlalchemy.orm import Session
from sqlalchemy import select

from src.infrastructure.db.models import SeatInventory
from src.domain.exceptions import InsufficientInventoryError


class SeatRepository:

    def __init__(self, db: Session):
        self.db = db

    def lock_inventory(self, event_id: str) -> SeatInventory:
        """
        SELECT ... FOR UPDATE
        Prevents race conditions.
        """

        stmt = (
            select(SeatInventory)
            .where(SeatInventory.event_id == event_id)
            .with_for_update()
        )

        inventory = self.db.execute(stmt).scalar_one_or_none()

        if not inventory:
            raise ValueError("Inventory not found")

        return inventory

    def get_by_event_id(self, event_id: str) -> SeatInventory | None:
        stmt = select(SeatInventory).where(SeatInventory.event_id == event_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create_or_reset_inventory(
        self,
        event_id: str,
        total_seats: int,
    ) -> SeatInventory:
        inventory = self.get_by_event_id(event_id)

        if inventory:
            inventory.total_seats = total_seats
            inventory.available_seats = total_seats
            return inventory

        inventory = SeatInventory(
            event_id=event_id,
            total_seats=total_seats,
            available_seats=total_seats,
        )
        self.db.add(inventory)
        return inventory

    def decrement_inventory(
        self,
        event_id: str,
        seat_count: int,
    ) -> None:

        inventory.available_seats -= seat_count

    def increment_inventory(
        self,
        event_id: str,
        seat_count: int,
    ) -> None:

        inventory = self.lock_inventory(event_id)
        inventory.available_seats += seat_count
