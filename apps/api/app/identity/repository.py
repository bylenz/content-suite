"""Repository for identity and RBAC persistence."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.identity.models import Brand, BrandMembership, Profile


def get_profile(session: Session, profile_id: uuid.UUID) -> Profile | None:
    return session.get(Profile, profile_id)


def list_memberships(session: Session, profile_id: uuid.UUID) -> Sequence[BrandMembership]:
    stmt = (
        select(BrandMembership)
        .where(BrandMembership.profile_id == profile_id)
        .join(Brand)
        .order_by(Brand.slug)
    )
    return list(session.scalars(stmt))


def get_membership(
    session: Session, profile_id: uuid.UUID, brand_id: uuid.UUID
) -> BrandMembership | None:
    stmt = select(BrandMembership).where(
        BrandMembership.profile_id == profile_id, BrandMembership.brand_id == brand_id
    )
    return session.scalars(stmt).first()
