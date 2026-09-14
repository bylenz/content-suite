"""Domain policies for creative: role gates and workflow transition validation."""

import uuid

from app.creative.models import CreativeWorkflowStatus
from app.identity.models import BrandRole
from app.identity.policies import authorize_brand_action

READER_ROLES = (BrandRole.CREATOR, BrandRole.CONTENT_REVIEWER, BrandRole.VISUAL_REVIEWER)
WRITER_ROLES = (BrandRole.CREATOR,)

# New versions can only be authored while the item is back with the creator.
EDITABLE_STATUSES = frozenset(
    {CreativeWorkflowStatus.DRAFT, CreativeWorkflowStatus.CONTENT_CHANGES_REQUESTED}
)


class InvalidWorkflowTransitionError(Exception):
    """Raised when a creative workflow transition or precondition is not satisfiable."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        # Keep details JSON-serializable for the error envelope (uuid -> str, None stays None).
        self.details = {
            key: str(value) if isinstance(value, uuid.UUID) else value
            for key, value in (details or {}).items()
        }


def require_reader(membership) -> None:
    """Any brand membership may read creative content (reviewers are read-only)."""
    authorize_brand_action(membership, READER_ROLES)


def require_writer(membership) -> None:
    """Only CREATOR members may create, edit, generate or submit creative content."""
    authorize_brand_action(membership, WRITER_ROLES)
