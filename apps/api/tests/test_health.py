"""Health endpoints: liveness without dependencies, readiness with DB check."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import get_session
from app.main import app


def test_live_is_ok_without_any_dependency(client: TestClient):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "live"}


def test_ready_is_ok_when_database_answers(client: TestClient):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_fails_when_database_is_unavailable(client: TestClient):
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
    assert response.status_code == 503
