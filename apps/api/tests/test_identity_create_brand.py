"""Self-serve workspace creation: POST /brands makes the caller CREATOR."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.identity.models import Brand, BrandMembership, Profile
from app.main import app
from tests.conftest import auth_header, make_token


def test_fresh_identity_with_no_profile_becomes_creator_of_a_new_brand(
    client: TestClient, session: Session
) -> None:
    token = make_token(email="new.user@example.com")

    response = client.post(
        "/api/v1/brands", headers=auth_header(token), json={"name": "Acme Foods"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["brand_name"] == "Acme Foods"
    assert body["brand_slug"] == "acme-foods"
    assert body["role"] == "CREATOR"

    brand = session.scalar(select(Brand).where(Brand.slug == "acme-foods"))
    assert brand is not None
    membership = session.scalar(
        select(BrandMembership).where(BrandMembership.brand_id == brand.id)
    )
    assert membership is not None and membership.role.value == "CREATOR"


def test_profile_is_provisioned_on_first_brand_creation(
    client: TestClient, session: Session
) -> None:
    token = make_token(email="second.user@example.com")

    response = client.post(
        "/api/v1/brands", headers=auth_header(token), json={"name": "Second Brand"}
    )

    assert response.status_code == 201
    profile_count = session.scalar(
        select(Profile).where(Profile.email == "second.user@example.com")
    )
    assert profile_count is not None


def test_me_reflects_the_newly_created_brand(client: TestClient) -> None:
    token = make_token(email="third.user@example.com")
    client.post("/api/v1/brands", headers=auth_header(token), json={"name": "Third Brand"})

    response = client.get("/api/v1/me", headers=auth_header(token))

    assert response.status_code == 200
    memberships = response.json()["memberships"]
    assert len(memberships) == 1
    assert memberships[0]["brand_slug"] == "third-brand"
    assert memberships[0]["role"] == "CREATOR"


def test_duplicate_name_gets_a_disambiguated_slug(client: TestClient) -> None:
    token_a = make_token(email="dup.a@example.com")
    token_b = make_token(email="dup.b@example.com")

    first = client.post(
        "/api/v1/brands", headers=auth_header(token_a), json={"name": "Overlap"}
    )
    second = client.post(
        "/api/v1/brands", headers=auth_header(token_b), json={"name": "Overlap"}
    )

    assert first.status_code == second.status_code == 201
    assert first.json()["brand_slug"] == "overlap"
    assert second.json()["brand_slug"] == "overlap-2"


def test_creating_a_second_brand_adds_a_second_membership_not_replaces_the_first(
    client: TestClient,
) -> None:
    token = make_token(email="multi.brand@example.com")
    client.post("/api/v1/brands", headers=auth_header(token), json={"name": "First One"})
    client.post("/api/v1/brands", headers=auth_header(token), json={"name": "Second One"})

    response = client.get("/api/v1/me", headers=auth_header(token))

    slugs = {m["brand_slug"] for m in response.json()["memberships"]}
    assert slugs == {"first-one", "second-one"}


def test_name_is_slugified_and_stripped_of_special_characters(client: TestClient) -> None:
    token = make_token(email="slug.test@example.com")

    response = client.post(
        "/api/v1/brands", headers=auth_header(token), json={"name": "  Café & Co.!!  "}
    )

    assert response.status_code == 201
    assert response.json()["brand_slug"] == "caf-co"


def test_missing_name_is_422(client: TestClient) -> None:
    token = make_token(email="empty.name@example.com")

    response = client.post("/api/v1/brands", headers=auth_header(token), json={"name": ""})

    assert response.status_code == 422


def test_extra_field_is_rejected(client: TestClient) -> None:
    token = make_token(email="extra.field@example.com")

    response = client.post(
        "/api/v1/brands",
        headers=auth_header(token),
        json={"name": "Valid Name", "slug": "attacker-chosen"},
    )

    assert response.status_code == 422


def test_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/v1/brands", json={"name": "No Auth"})

    assert response.status_code == 401


def test_identity_without_email_claim_is_422(client: TestClient) -> None:
    token = make_token(email=None)

    response = client.post("/api/v1/brands", headers=auth_header(token), json={"name": "X"})

    assert response.status_code == 422


def test_email_outside_the_allowlist_is_403(client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        brand_creation_allowlist="allowed@example.com"
    )
    try:
        token = make_token(email="stranger@example.com")
        response = client.post(
            "/api/v1/brands", headers=auth_header(token), json={"name": "Nope"}
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 403


def test_email_on_the_allowlist_is_matched_case_insensitively(
    client: TestClient, session: Session
) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        brand_creation_allowlist="Allowed@Example.com"
    )
    try:
        token = make_token(email="allowed@example.com")
        response = client.post(
            "/api/v1/brands", headers=auth_header(token), json={"name": "Yes"}
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 201


def test_empty_allowlist_blocks_everyone(client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(brand_creation_allowlist="")
    try:
        token = make_token(email="anyone@example.com")
        response = client.post(
            "/api/v1/brands", headers=auth_header(token), json={"name": "Blocked"}
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 403


def test_wildcard_allowlist_allows_anyone(client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(brand_creation_allowlist="*")
    try:
        token = make_token(email="whoever@example.com")
        response = client.post(
            "/api/v1/brands", headers=auth_header(token), json={"name": "Wildcard"}
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 201
