"""Explicit storage module errors. No HTTP mapping here: handlers are
registered centrally in `app/errors.py` (storage 503s / file validation 422),
same shape as `app.ai.errors`."""


class StorageNotConfiguredError(Exception):
    """Raised when a storage operation runs with no configured adapter (resolver returned None)."""

    def __init__(self, operation: str) -> None:
        super().__init__(f"Storage is not configured for operation '{operation}'")
        self.operation = operation


class StorageValidationError(Exception):
    """Raised when an uploaded file fails server-side validation (size/magic bytes)."""

    def __init__(self, message: str, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


class StorageUnavailableError(Exception):
    """Raised when a configured storage adapter fails at runtime (network/SDK error).

    `cause` never leaves this module in a response: the API boundary
    sanitizes to the operation name only.
    """

    def __init__(self, operation: str, cause: Exception | None = None) -> None:
        super().__init__(f"Storage operation '{operation}' failed")
        self.operation = operation
        self.cause = cause
