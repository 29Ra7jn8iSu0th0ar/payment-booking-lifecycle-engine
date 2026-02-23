

class DistrictIntegrityError(Exception):
    """
    Base exception for all domain-level errors
    inside the District Integrity Engine.
    """


class InvalidStateTransitionError(DistrictIntegrityError):
    """
    Raised when an illegal booking state transition is attempted.
    """

    def __init__(self, from_state: str, to_state: str):
        self.from_state = from_state
        self.to_state = to_state

        message = (
            f"Illegal state transition attempted: "
            f"{from_state} -> {to_state}"
        )
        super().__init__(message)


class InsufficientInventoryError(DistrictIntegrityError):
    """Raised when no seats are available."""


class IdempotencyConflictError(DistrictIntegrityError):
    """Raised when an idempotent request conflicts with previous data."""