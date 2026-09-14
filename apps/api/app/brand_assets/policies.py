"""Domain policies for brand_assets: role gates reusing identity's membership policy.

403 vs 404 (design.md, mirrors `011-creative-studio`'s `create_item`/`_resolve_item`
precedent): upload and list protect no existing resource, so a non-member gets
403 straight from `authorize_brand_action` (see `app.brand_assets.service`).
Delete protects an existing `asset_id`, so the service resolves the asset and
membership first and answers 404 uniformly for "doesn't exist" / "belongs to
another brand" / "caller isn't a member" -- only a member with the wrong role
reaches this module's `require_writer` and gets 403.
"""

from app.identity.models import BrandRole
from app.identity.policies import authorize_brand_action

READER_ROLES = (BrandRole.CREATOR, BrandRole.CONTENT_REVIEWER, BrandRole.VISUAL_REVIEWER)
WRITER_ROLES = (BrandRole.CREATOR,)


def require_reader(membership) -> None:
    """Any brand member may list brand assets (incl. Visual Compliance Reviewer)."""
    authorize_brand_action(membership, READER_ROLES)


def require_writer(membership) -> None:
    """Only CREATOR members may upload, replace or delete a brand asset."""
    authorize_brand_action(membership, WRITER_ROLES)
