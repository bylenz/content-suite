"""Domain policies for brand_dna: role gates reusing identity's membership policy."""

import uuid

from app.identity.models import BrandRole
from app.identity.policies import authorize_brand_action

READER_ROLES = (BrandRole.CREATOR, BrandRole.CONTENT_REVIEWER, BrandRole.VISUAL_REVIEWER)
WRITER_ROLES = (BrandRole.CREATOR,)


class InvalidWorkflowTransitionError(Exception):
    """Raised when a version transition or publish precondition is not satisfiable."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        # Keep details JSON-serializable for the error envelope (uuid -> str, None stays None).
        self.details = {
            key: str(value) if isinstance(value, uuid.UUID) else value
            for key, value in (details or {}).items()
        }


def require_reader(membership) -> None:
    """Any brand membership may read published Brand DNA (draft visibility is role-gated)."""
    authorize_brand_action(membership, READER_ROLES)


def require_writer(membership) -> None:
    """Only CREATOR members may create, edit or publish Brand DNA."""
    authorize_brand_action(membership, WRITER_ROLES)
