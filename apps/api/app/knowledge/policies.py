"""Domain policies for knowledge: membership gates mirroring brand_dna."""

from app.identity.models import BrandRole
from app.identity.policies import authorize_brand_action

READER_ROLES = (BrandRole.CREATOR, BrandRole.CONTENT_REVIEWER, BrandRole.VISUAL_REVIEWER)
SYNC_ROLES = (BrandRole.CREATOR,)


def require_reader(membership) -> None:
    """Any brand membership may read published knowledge chunks and status."""
    authorize_brand_action(membership, READER_ROLES)


def require_sync_creator(membership) -> None:
    """Only CREATOR members may trigger the explicit knowledge sync."""
    authorize_brand_action(membership, SYNC_ROLES)
