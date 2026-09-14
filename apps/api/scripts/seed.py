"""Idempotent demo seeds: Kinu brand, demo profiles and per-role memberships.

Run from apps/api with: uv run python -m scripts.seed

All lookups use natural keys (slug, email, profile+brand), so repeating the
script never duplicates data. Deterministic UUIDs let tests and the dev token
utility reference the seeded profiles without extra lookups.
"""

import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_engine
from app.identity.models import Brand, BrandMembership, BrandRole, Profile

KINU_BRAND_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
CREATOR_PROFILE_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
CONTENT_REVIEWER_PROFILE_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
VISUAL_REVIEWER_PROFILE_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")

BRAND = {"id": KINU_BRAND_ID, "name": "Kinu", "slug": "kinu"}

PROFILES = (
    {"id": CREATOR_PROFILE_ID, "email": "lenin@kinu.example", "display_name": "Lenin"},
    {
        "id": CONTENT_REVIEWER_PROFILE_ID,
        "email": "content.reviewer@kinu.example",
        "display_name": "Kinu Content Reviewer",
    },
    {
        "id": VISUAL_REVIEWER_PROFILE_ID,
        "email": "visual.reviewer@kinu.example",
        "display_name": "Kinu Visual Reviewer",
    },
)

MEMBERSHIPS = (
    (CREATOR_PROFILE_ID, BrandRole.CREATOR),
    (CONTENT_REVIEWER_PROFILE_ID, BrandRole.CONTENT_REVIEWER),
    (VISUAL_REVIEWER_PROFILE_ID, BrandRole.VISUAL_REVIEWER),
)


def seed(session: Session) -> dict[str, int]:
    """Create missing demo entities and return how many were created vs. already present."""
    created = {"brands": 0, "profiles": 0, "memberships": 0}

    if session.scalar(select(Brand).where(Brand.slug == BRAND["slug"])) is None:
        session.add(Brand(**BRAND))
        created["brands"] += 1

    profile_ids = {p["id"] for p in PROFILES}
    existing_profiles = set(session.scalars(select(Profile.id).where(Profile.id.in_(profile_ids))))
    for profile in PROFILES:
        if profile["id"] not in existing_profiles:
            session.add(Profile(**profile))
            created["profiles"] += 1

    membership_pairs = {
        (m.profile_id, m.brand_id)
        for m in session.scalars(
            select(BrandMembership).where(BrandMembership.brand_id == KINU_BRAND_ID)
        )
    }
    for profile_id, role in MEMBERSHIPS:
        if (profile_id, KINU_BRAND_ID) not in membership_pairs:
            session.add(
                BrandMembership(
                    id=uuid.uuid4(), profile_id=profile_id, brand_id=KINU_BRAND_ID, role=role
                )
            )
            created["memberships"] += 1

    session.commit()
    return created


def main() -> None:
    with Session(get_engine()) as session:
        created = seed(session)
    print(json.dumps({"seed": "kinu-demo", "created": created}, indent=2))


if __name__ == "__main__":
    main()
