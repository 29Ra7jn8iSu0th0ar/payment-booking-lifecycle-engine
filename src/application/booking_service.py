from sqlalchemy.orm import Session

from src.domain.state_machine import BookingStateMachine, BookingStatus
from src.infrastructure.db.models import Booking
from src.infrastructure.repositories.booking_repository import BookingRepository
from src.infrastructure.repositories.seat_repository import SeatRepository


class BookingService:
    """Application service coordinating booking workflow."""

    def __init__(self, db: Session):
        self.db = db
        self.booking_repository = BookingRepository(db)
        self.seat_repository = SeatRepository(db)

    def create_booking(
        self,
        user_id: str,
        event_id: str,
        seat_count: int,
        idempotency_key: str,
    ) -> Booking:
        booking = self.booking_repository.create_booking(
            user_id=user_id,
            event_id=event_id,
            seat_count=seat_count,
            idempotency_key=idempotency_key,
        )

        self._transition(booking, BookingStatus.PENDING_PAYMENT)
        self.seat_repository.decrement_inventory(event_id, seat_count)
        self._transition(booking, BookingStatus.SUCCESS)


    def confirm_payment(
        self,
        booking_id: str,
        result: str,
    ) -> Booking:
        booking = self.booking_repository.get_by_id(booking_id)

        if not booking:
            raise ValueError("Booking not found")

        if result == "success":
            self._transition(booking, BookingStatus.SUCCESS)
        elif result == "failed":
            self._transition(booking, BookingStatus.FAILED)
            self.seat_repository.increment_inventory(
                booking.event_id,
                booking.seat_count,
            )
        else:
            raise ValueError("Invalid payment result")

        self.db.flush()
        self.db.refresh(booking)
        return booking

    def _transition(self, booking: Booking, to_status: BookingStatus) -> None:
        BookingStateMachine.validate_transition(booking.status, to_status)
        self.booking_repository.update_status(booking, to_status)
