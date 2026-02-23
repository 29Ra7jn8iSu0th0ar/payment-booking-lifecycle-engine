# src/domain/state_machine.py

from enum import Enum
from typing import Dict, Set

from src.domain.exceptions import InvalidStateTransitionError


class BookingStatus(str, Enum):
    INITIATED = "INITIATED"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUND_PENDING = "REFUND_PENDING"
    REFUNDED = "REFUNDED"


class BookingStateMachine:
    """
    Central lifecycle controller for booking transitions.
    Defines the legal state transitions.
    """

    _ALLOWED_TRANSITIONS: Dict[BookingStatus, Set[BookingStatus]] = {
        BookingStatus.INITIATED: {
            BookingStatus.PENDING_PAYMENT,
            BookingStatus.FAILED,
        },
        BookingStatus.PENDING_PAYMENT: {
            BookingStatus.SUCCESS,
            BookingStatus.FAILED,
        },
        BookingStatus.SUCCESS: {
            BookingStatus.REFUND_PENDING,
        },
        BookingStatus.REFUND_PENDING: {
            BookingStatus.REFUNDED,
        },
        BookingStatus.FAILED: set(),
        BookingStatus.REFUNDED: set(),
    }

    @classmethod
    def can_transition(
        cls,
        from_status: BookingStatus,
        to_status: BookingStatus,
    ) -> bool:
        """
        Returns True if transition is allowed.
        """
        cls._ensure_valid_status(from_status)
        cls._ensure_valid_status(to_status)

        return to_status in cls._ALLOWED_TRANSITIONS.get(from_status, set())

    @classmethod
    def validate_transition(
        cls,
        from_status: BookingStatus,
        to_status: BookingStatus,
    ) -> None:
        """
        Raises InvalidStateTransitionError if transition is illegal.
        """
        if not cls.can_transition(from_status, to_status):
            raise InvalidStateTransitionError(
                from_state=from_status.value,
                to_state=to_status.value,
            )

    @classmethod
    def is_terminal(cls, status: BookingStatus) -> bool:
        """
        Returns True if the state is terminal (no further transitions allowed).
        """
        cls._ensure_valid_status(status)
        return len(cls._ALLOWED_TRANSITIONS.get(status, set())) == 0

    @classmethod
    def get_allowed_transitions(
        cls, status: BookingStatus
    ) -> Set[BookingStatus]:
        """
        Returns allowed next states from current state.
        """
        cls._ensure_valid_status(status)
        return cls._ALLOWED_TRANSITIONS.get(status, set())

    @staticmethod
    def _ensure_valid_status(status: BookingStatus) -> None:
        """
        Defensive guard against invalid status types.
        """
        if not isinstance(status, BookingStatus):
            raise TypeError(
                f"Expected BookingStatus, got {type(status)}"
            )
