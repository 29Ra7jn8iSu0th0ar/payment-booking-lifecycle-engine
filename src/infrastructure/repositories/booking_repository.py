# src/infrastructure/repositories/booking_repository.py

from sqlalchemy.orm import Session
from sqlalchemy import select

from src.infrastructure.db.models import Booking
from src.domain.exceptions import IdempotencyConflictError
from src.domain.state_machine import BookingStatus


class BookingRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> Booking | None:
        
        stmt = select(Booking).where(
            Booking.idempotency_key == idempotency_key
        )

        
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_id(
        self,
        booking_id: str,
    ) -> Booking | None:

        stmt = select(Booking).where(Booking.id == booking_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create_booking(
        self,
        user_id: str,
        event_id: str,
        seat_count: int,
        idempotency_key: str,
    ) -> Booking:

        # Idempotency Check
        existing = self.get_by_idempotency_key(idempotency_key)

        if existing:
            raise IdempotencyConflictError(
                "Duplicate idempotent request"
            )

        booking = Booking(
            user_id=user_id,
            event_id=event_id,
            seat_count=seat_count,
            idempotency_key=idempotency_key,
            status=BookingStatus.INITIATED,
        )

        self.db.add(booking)
        return booking

    def update_status(
        self,
        booking: Booking,
        new_status: BookingStatus,
    ) -> None:

        booking.status = new_status
