"""/api/v1/me authentication boundary: verified JWT identity, server-side memberships."""

import base64
import json
import uuid

from sqlalchemy.orm import Session

from app.identity.models import Brand, BrandMembership, BrandRole, Profile
from tests.conftest import make_token


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def seed_membership(session: Session, role: BrandRole) -> tuple[uuid.UUID, uuid.UUID]:
    profile = Profile(id=uuid.uuid4(), email="seeded@example.com", display_name="Seeded")
    brand = Brand(id=uuid.uuid4(), name="Acme", slug="acme")
    session.add_all(
        [
            profile,
            brand,
            BrandMembership(id=uuid.uuid4(), profile_id=profile.id, brand_id=brand.id, role=role),
        ]
    )
    session.commit()
    return profile.id, brand.id


def test_me_without_token_is_unauthenticated(client):
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_with_malformed_token_is_unauthenticated(client):
    response = client.get("/api/v1/me", headers=auth_header("not-a-jwt"))
    assert response.status_code == 401


def test_me_with_wrong_secret_is_unauthenticated(client):
    token = make_token(secret="attacker-secret-0123456789abcdef012345")
    response = client.get("/api/v1/me", headers=auth_header(token))
    assert response.status_code == 401


def test_me_with_unallowed_algorithm_is_unauthenticated(client):
    # Hand-crafted alg=none token must never be accepted.
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(
        b"="
    )
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": str(uuid.uuid4()), "email": "x@example.com"}).encode()
    ).rstrip(b"=")
    token = f"{header.decode()}.{payload.decode()}."
    response = client.get("/api/v1/me", headers=auth_header(token))
    assert response.status_code == 401


def test_me_with_expired_token_is_unauthenticated(client):
    from datetime import timedelta

    token = make_token(expires_in=timedelta(seconds=-60))
    response = client.get("/api/v1/me", headers=auth_header(token))
    assert response.status_code == 401


def test_me_without_expiry_claim_is_unauthenticated(client):
    # exp is required: non-expiring tokens must never be accepted.
    token = make_token(expires_in=None)
    response = client.get("/api/v1/me", headers=auth_header(token))
    assert response.status_code == 401


def test_me_with_wrong_audience_is_unauthenticated(client):
    token = make_token(aud="some-other-api")
    response = client.get("/api/v1/me", headers=auth_header(token))
    assert response.status_code == 401


def test_me_with_wrong_issuer_is_unauthenticated(client):
    token = make_token(iss="https://attacker.example.com/auth/v1")
    response = client.get("/api/v1/me", headers=auth_header(token))
    assert response.status_code == 401


def test_me_without_subject_is_unauthenticated(client):
    token = make_token(sub="")
    response = client.get("/api/v1/me", headers=auth_header(token))
    assert response.status_code == 401


def test_me_with_valid_token_returns_identity(client, session):
    profile_id, brand_id = seed_membership(session, BrandRole.CONTENT_REVIEWER)
    # Role claim in the token is a lie; roles must come from the database.
    token = make_token(sub=str(profile_id), email="seeded@example.com", role="CREATOR")

    response = client.get("/api/v1/me", headers=auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(profile_id)
    assert body["email"] == "seeded@example.com"
    assert body["display_name"] == "Seeded"
    assert body["memberships"] == [
        {
            "brand_id": str(brand_id),
            "brand_name": "Acme",
            "brand_slug": "acme",
            "role": "CONTENT_REVIEWER",
        }
    ]


def test_me_with_valid_token_and_no_profile_returns_token_identity(client, session):
    token = make_token(email="ghost@example.com")

    response = client.get("/api/v1/me", headers=auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "ghost@example.com"
    assert body["display_name"] is None
    assert body["memberships"] == []
