"""Domain policy for the activity feed: any brand member may read it (change 014)."""

from app.identity.models import BrandRole
from app.identity.policies import authorize_brand_action

VIEWER_ROLES = (BrandRole.CREATOR, BrandRole.CONTENT_REVIEWER, BrandRole.VISUAL_REVIEWER)


def require_reader(membership) -> None:
    authorize_brand_action(membership, VIEWER_ROLES)
