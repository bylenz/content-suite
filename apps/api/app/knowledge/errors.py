"""Domain errors for the knowledge module.

`KnowledgeNotAvailableError` deliberately has NO HTTP handler in this change:
internal consumers (Creative/Visual Audit, specs 04-06) raise it and map it to
503 at their own API boundary (API.md). `SyncConflictError` maps to 409 via the
centralized error envelope (reason field distinguishes concurrent sync vs
OUTDATED).
"""

import uuid


class SyncConflictError(Exception):
    """Raised when a sync cannot start: concurrent sync in progress or OUTDATED."""

    def __init__(self, message: str, reason: str, version_id: uuid.UUID) -> None:
        super().__init__(message)
        self.details = {"reason": reason, "brand_dna_version_id": str(version_id)}


class KnowledgeNotAvailableError(Exception):
    """Fail-safe: Knowledge context cannot be built (never partial context)."""
