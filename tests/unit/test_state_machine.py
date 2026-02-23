# tests/unit/test_state_machine.py

import pytest

from src.domain.state_machine import BookingStateMachine, BookingStatus
from src.domain.exceptions import InvalidStateTransitionError


# ---------------------
# VALID TRANSITIONS
# ---------------------

def test_valid_happy_path():
    assert BookingStateMachine.can_transition(
        BookingStatus.INITIATED,
        BookingStatus.PENDING_PAYMENT,
    )

    assert BookingStateMachine.can_transition(
        BookingStatus.PENDING_PAYMENT,
        BookingStatus.SUCCESS,
    )

    assert BookingStateMachine.can_transition(
        BookingStatus.SUCCESS,
        BookingStatus.REFUND_PENDING,
    )

    assert BookingStateMachine.can_transition(
        BookingStatus.REFUND_PENDING,
        BookingStatus.REFUNDED,
    )


# ---------------------
# INVALID TRANSITIONS
# ---------------------

def test_cannot_skip_payment():
    with pytest.raises(InvalidStateTransitionError):
        BookingStateMachine.validate_transition(
            BookingStatus.INITIATED,
            BookingStatus.SUCCESS,
        )


def test_terminal_state_failed():
    assert BookingStateMachine.is_terminal(BookingStatus.FAILED)

    with pytest.raises(InvalidStateTransitionError):
        BookingStateMachine.validate_transition(
            BookingStatus.FAILED,
            BookingStatus.SUCCESS,
        )


def test_terminal_state_refunded():
    assert BookingStateMachine.is_terminal(BookingStatus.REFUNDED)

    with pytest.raises(InvalidStateTransitionError):
        BookingStateMachine.validate_transition(
            BookingStatus.REFUNDED,
            BookingStatus.SUCCESS,
        )


def test_invalid_type_guard():
    with pytest.raises(TypeError):
        BookingStateMachine.validate_transition(
            "INITIATED",  # invalid type
            BookingStatus.SUCCESS,
        )
