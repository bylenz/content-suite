"""Demo seeds: idempotency and /api/v1/me membership resolution."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.identity.models import Brand, BrandMembership, Profile
from scripts import seed as seed_module
from tests.conftest import TEST_JWT_ISSUER, auth_header, make_token


def test_seed_is_idempotent(session: Session):
    first = seed_module.seed(session)
    assert first == {"brands": 1, "profiles": 3, "memberships": 3}

    second = seed_module.seed(session)
    assert second == {"brands": 0, "profiles": 0, "memberships": 0}

    # Scoped to the seed's natural keys: the shared test database also carries
    # unrelated brands/profiles created by other tests.
    assert session.scalar(select(func.count()).select_from(Brand).where(Brand.slug == "kinu")) == 1
    assert (
        session.scalar(
            select(func.count()).select_from(Profile).where(Profile.email.endswith("@kinu.example"))
        )
        == 3
    )
    assert (
        session.scalar(
            select(func.count())
            .select_from(BrandMembership)
            .where(BrandMembership.brand_id == seed_module.KINU_BRAND_ID)
        )
        == 3
    )


def test_seeded_memberships_resolve_through_me(client: TestClient, session: Session):
    seed_module.seed(session)

    token = make_token(
        sub=str(seed_module.CREATOR_PROFILE_ID),
        email="creator@kinu.example",
        iss=TEST_JWT_ISSUER,
    )

    response = client.get("/api/v1/me", headers=auth_header(token))

    assert response.status_code == 200
    memberships = response.json()["memberships"]
    assert len(memberships) == 1
    assert memberships[0]["brand_slug"] == "kinu"
    assert memberships[0]["role"] == "CREATOR"
