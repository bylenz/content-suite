"""Application service for the identity module."""

from sqlalchemy.orm import Session

from app.identity import repository
from app.identity.auth import AuthenticatedUser
from app.identity.schemas import Me, MembershipOut


def get_me(session: Session, user: AuthenticatedUser) -> Me:
    profile = repository.get_profile(session, user.id)
    memberships = repository.list_memberships(session, user.id)
    return Me(
        id=user.id,
        email=profile.email if profile else user.email,
        display_name=profile.display_name if profile else None,
        memberships=[
            MembershipOut(
                brand_id=m.brand_id,
                brand_name=m.brand.name,
                brand_slug=m.brand.slug,
                role=m.role,
            )
            for m in memberships
        ],
    )
