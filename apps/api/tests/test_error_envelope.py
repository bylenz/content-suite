"""Centralized error envelope: exact shape for 401/403/404/409/422/503."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.db import get_session
from app.identity.models import BrandRole
from app.main import app
from tests.conftest import auth_header, make_workspace, valid_document
from tests.test_brand_dna_reads import create_and_publish


def assert_envelope(response, status_code: int, code: str, details: dict) -> None:
    assert response.status_code == status_code
    assert response.json() == {
        "error": {"code": code, "message": response.json()["error"]["message"], "details": details}
    }
    assert response.json()["error"]["message"]


def test_unauthenticated_is_401_envelope_with_challenge(client: TestClient):
    response = client.get("/api/v1/me")
    assert_envelope(response, 401, "UNAUTHENTICATED", {})
    assert response.headers["www-authenticate"] == "Bearer"


def test_invalid_token_is_401_envelope(client: TestClient):
    response = client.get("/api/v1/me", headers=auth_header("not-a-jwt"))
    assert_envelope(response, 401, "UNAUTHENTICATED", {})


def test_permission_denied_is_403_envelope(client: TestClient, session: Session):
    workspace = make_workspace(session)

    response = client.patch(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/draft",
        headers=auth_header(workspace["tokens"][BrandRole.CONTENT_REVIEWER]),
        json={"document": valid_document()},
    )

    assert_envelope(response, 403, "PERMISSION_DENIED", {})


def test_unknown_route_is_404_envelope(client: TestClient):
    assert_envelope(client.get("/api/v1/does-not-exist"), 404, "NOT_FOUND", {})


def test_missing_version_is_404_envelope(client: TestClient, session: Session):
    workspace = make_workspace(session)
    create_and_publish(client, workspace)

    response = client.get(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/versions/42",
        headers=auth_header(workspace["tokens"][BrandRole.CREATOR]),
    )

    assert_envelope(response, 404, "NOT_FOUND", {})


def test_publish_conflict_is_409_envelope_with_details(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    active = create_and_publish(client, workspace)

    response = client.post(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/publish",
        headers=auth_header(creator_token),
        json={"expected_draft_id": "00000000-0000-4000-8000-000000000000"},
    )

    assert_envelope(
        response,
        409,
        "INVALID_WORKFLOW_TRANSITION",
        {
            "expected_draft_id": "00000000-0000-4000-8000-000000000000",
            "active_version_id": active["id"],
        },
    )


def test_invalid_document_is_422_envelope_with_field_paths(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    document = valid_document()
    document["identity"]["purpose"] = ""

    response = client.patch(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/draft",
        headers=auth_header(workspace["tokens"][BrandRole.CREATOR]),
        json={"document": document},
    )

    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "VALIDATION_ERROR"
    assert "body.document.identity.purpose" in body["details"]["field_errors"]


def test_readiness_without_database_is_503_envelope(client: TestClient):
    broken_engine = create_engine(
        "sqlite:////nonexistent-dir/content_suite_test.db",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    def broken_session():
        with Session(broken_engine) as session:
            yield session

    app.dependency_overrides[get_session] = broken_session
    try:
        response = client.get("/health/ready")
    finally:
        app.dependency_overrides.clear()
        broken_engine.dispose()

    assert_envelope(response, 503, "SERVICE_UNAVAILABLE", {})


def test_unconfigured_auth_is_503_envelope(client: TestClient):
    app.dependency_overrides[get_settings] = lambda: Settings(
        auth_jwt_secret="", auth_jwt_issuer=""
    )
    try:
        response = client.get("/api/v1/me", headers=auth_header("any-token"))
    finally:
        app.dependency_overrides.clear()

    assert_envelope(response, 503, "SERVICE_UNAVAILABLE", {})


def test_identity_errors_use_the_shared_envelope(client: TestClient):
    """/me 401s flow through the same centralized handler (design: envelope applies
    to identity and health endpoints too)."""
    response = client.get("/api/v1/me")
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert response.json()["error"]["details"] == {}
