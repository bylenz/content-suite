"""Settings (008 task 1.3): storage settings default to empty/safe and never
fail startup; env values are read verbatim, no secrets hardcoded."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app, create_app


def test_storage_settings_default_to_empty_and_safe_when_unconfigured() -> None:
    # _env_file=None isolates the test from any local .env values.
    settings = Settings(_env_file=None)
    assert settings.storage_project_url == ""
    assert settings.storage_service_key == ""
    assert settings.storage_bucket == ""
    assert settings.storage_signed_url_ttl_seconds == 300
    assert settings.storage_max_upload_bytes == 5 * 1024 * 1024


def test_storage_settings_read_values_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("CONTENT_SUITE_STORAGE_PROJECT_URL", "https://proj.supabase.co")
    monkeypatch.setenv("CONTENT_SUITE_STORAGE_SERVICE_KEY", "service-key-test")
    monkeypatch.setenv("CONTENT_SUITE_STORAGE_BUCKET", "visuals-test")
    monkeypatch.setenv("CONTENT_SUITE_STORAGE_SIGNED_URL_TTL_SECONDS", "120")
    monkeypatch.setenv("CONTENT_SUITE_STORAGE_MAX_UPLOAD_BYTES", "1048576")
    settings = Settings(_env_file=None)
    assert settings.storage_project_url == "https://proj.supabase.co"
    assert settings.storage_service_key == "service-key-test"
    assert settings.storage_bucket == "visuals-test"
    assert settings.storage_signed_url_ttl_seconds == 120
    assert settings.storage_max_upload_bytes == 1048576


def test_app_starts_without_storage_configuration() -> None:
    fresh = create_app()
    assert fresh.title == app.title
    with TestClient(fresh) as client:
        assert client.get("/health/live").status_code == 200
