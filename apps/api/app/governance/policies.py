"""Domain policies for governance: role gates reusing identity's membership policy."""

import uuid

from app.identity.models import BrandRole
from app.identity.policies import authorize_brand_action

READER_ROLES = (BrandRole.CREATOR, BrandRole.CONTENT_REVIEWER)
REVIEWER_ROLES = (BrandRole.CONTENT_REVIEWER,)


class InvalidWorkflowTransitionError(Exception):
    """Raised when a review decision or precondition is not satisfiable."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        # Keep details JSON-serializable for the error envelope (uuid -> str, None stays None).
        self.details = {
            key: str(value) if isinstance(value, uuid.UUID) else value
            for key, value in (details or {}).items()
        }


def require_reader(membership) -> None:
    """Creator (own item status/feedback) and Content Reviewer (queue/detail) may read."""
    authorize_brand_action(membership, READER_ROLES)


def require_reviewer(membership) -> None:
    """Only CONTENT_REVIEWER members may approve or request changes."""
    authorize_brand_action(membership, REVIEWER_ROLES)
