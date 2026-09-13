"""Domain policies for brand membership and role authorization."""

from collections.abc import Sequence

from app.identity.models import BrandMembership, BrandRole


class PermissionDeniedError(Exception):
    """Raised when a brand action is not authorized for the current user."""


def authorize_brand_action(
    membership: BrandMembership | None, allowed_roles: Sequence[BrandRole]
) -> None:
    """Allow the action only with an existing membership and an allowed role.

    Membership and role must be resolved server-side (repository lookup),
    never taken from client input.
    """
    if membership is None:
        raise PermissionDeniedError("User is not a member of this brand")
    if membership.role not in allowed_roles:
        raise PermissionDeniedError(f"Role {membership.role.value} is not allowed for this action")
