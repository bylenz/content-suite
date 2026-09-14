"""Application service for the identity module."""

import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.identity import repository
from app.identity.auth import AuthenticatedUser
from app.identity.models import Brand, BrandMembership, BrandRole, Profile
from app.identity.schemas import BrandCreateIn, Me, MembershipOut

# Bounded: a slug collision loop beyond this many attempts means something is
# wrong (e.g. many identically-named brands already exist), not a transient race.
_MAX_SLUG_ATTEMPTS = 50

_ALLOWLIST_WILDCARD = "*"


def _is_allowed_to_create_brand(email: str, settings: Settings) -> bool:
    allowlist = settings.brand_creation_allowlist
    if allowlist == [_ALLOWLIST_WILDCARD]:
        return True
    allowed = {entry.lower() for entry in allowlist}
    return email.lower() in allowed


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


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "brand"


def _unique_slug(session: Session, base_slug: str) -> str:
    for attempt in range(_MAX_SLUG_ATTEMPTS):
        candidate = base_slug if attempt == 0 else f"{base_slug}-{attempt + 1}"
        if not repository.slug_exists(session, candidate):
            return candidate
    raise HTTPException(
        status.HTTP_409_CONFLICT, "Could not find an available slug for this brand name"
    )


def create_brand(
    session: Session, user: AuthenticatedUser, payload: BrandCreateIn, settings: Settings
) -> MembershipOut:
    """Self-serve workspace creation: the caller becomes the brand's sole CREATOR.

    Gated by `settings.brand_creation_allowlist` -- any authenticated identity
    can reach this (there is no existing brand membership to check yet, that
    is exactly what this call grants), so the allowlist is the only thing
    stopping an arbitrary Supabase-authenticated stranger from provisioning
    their own workspace. The caller's `Profile` row is provisioned here on
    first use (nothing else in the app auto-creates it: today only the seed
    script does, for demo identities), since a real Supabase-authenticated
    user otherwise has none.
    """
    if not user.email:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Authenticated identity has no email claim; cannot provision a profile",
        )
    if not _is_allowed_to_create_brand(user.email, settings):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This email is not allowed to create a workspace",
        )
    profile = repository.get_profile(session, user.id)
    if profile is None:
        profile = Profile(id=user.id, email=user.email, display_name=None)
        session.add(profile)

    slug = _unique_slug(session, _slugify(payload.name))
    brand = Brand(id=uuid.uuid4(), name=payload.name, slug=slug)
    session.add(brand)
    membership = BrandMembership(
        id=uuid.uuid4(), profile_id=profile.id, brand_id=brand.id, role=BrandRole.CREATOR
    )
    session.add(membership)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A brand with that name was just created; try again"
        ) from exc

    return MembershipOut(
        brand_id=brand.id, brand_name=brand.name, brand_slug=brand.slug, role=membership.role
    )
