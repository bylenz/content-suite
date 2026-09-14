"""CORS configuration: explicit origin list vs. the "*" any-origin mode."""

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import Settings


def _preflight(client: TestClient, origin: str):
    return client.options(
        "/health/live",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )


def _client_with(monkeypatch: pytest.MonkeyPatch, cors_origins: str) -> TestClient:
    settings = Settings(cors_origins=cors_origins)
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    return TestClient(main.create_app())


def test_cors_origins_env_accepts_comma_separated_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CONTENT_SUITE_CORS_ORIGINS", "https://app.example.com, http://localhost:5173"
    )
    assert Settings().cors_origins == ["https://app.example.com", "http://localhost:5173"]


def test_wildcard_allows_any_origin_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client_with(monkeypatch, "*")

    response = _preflight(client, "https://preview-abc123.vercel.app")

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in response.headers


def test_explicit_list_rejects_unlisted_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client_with(monkeypatch, "https://app.example.com")

    allowed = _preflight(client, "https://app.example.com")
    rejected = _preflight(client, "https://evil.example.com")

    assert allowed.headers["access-control-allow-origin"] == "https://app.example.com"
    assert allowed.headers["access-control-allow-credentials"] == "true"
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers
