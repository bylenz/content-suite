"""Observability errors. Tracer problems always degrade to no-op with a
sanitized log; these types classify the failure inside the tracer boundary and
never propagate to domain operations."""


class TracerError(Exception):
    """Base class for tracer infrastructure failures."""


class TracerInitializationError(TracerError):
    """Raised when a real tracer cannot be constructed (SDK missing/broken)."""
