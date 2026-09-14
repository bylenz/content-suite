"""Settings (1.2): AI/Langfuse settings default to empty and never fail startup."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app, create_app


def test_settings_default_to_empty_when_unconfigured() -> None:
    # _env_file=None isolates the test from any local .env values.
    settings = Settings(_env_file=None)
    assert settings.ai_provider == ""
    assert settings.langfuse_public_key == ""
    assert settings.langfuse_secret_key == ""
    assert settings.langfuse_host == ""


def test_settings_read_values_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("CONTENT_SUITE_AI_PROVIDER", "langfuse-demo")
    monkeypatch.setenv("CONTENT_SUITE_LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("CONTENT_SUITE_LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setenv("CONTENT_SUITE_LANGFUSE_HOST", "https://langfuse.example")
    settings = Settings(_env_file=None)
    assert settings.ai_provider == "langfuse-demo"
    assert settings.langfuse_public_key == "pk-lf-test"
    assert settings.langfuse_secret_key == "sk-lf-test"
    assert settings.langfuse_host == "https://langfuse.example"


def test_app_starts_without_ai_configuration() -> None:
    fresh = create_app()
    assert fresh.title == app.title
    with TestClient(fresh) as client:
        assert client.get("/health/live").status_code == 200
