"""Membership and role policy: valid access, missing membership, invalid role."""

import pytest

from app.identity.models import BrandMembership, BrandRole
from app.identity.policies import PermissionDeniedError, authorize_brand_action


def membership_with_role(role: BrandRole) -> BrandMembership:
    return BrandMembership(role=role)


def test_valid_membership_and_role_is_allowed():
    authorize_brand_action(membership_with_role(BrandRole.CREATOR), [BrandRole.CREATOR])


def test_missing_membership_is_denied():
    with pytest.raises(PermissionDeniedError):
        authorize_brand_action(None, [BrandRole.CREATOR])


def test_role_not_in_allowed_roles_is_denied():
    membership = membership_with_role(BrandRole.CONTENT_REVIEWER)
    with pytest.raises(PermissionDeniedError):
        authorize_brand_action(membership, [BrandRole.CREATOR, BrandRole.VISUAL_REVIEWER])
