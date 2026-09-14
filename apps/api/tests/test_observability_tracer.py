"""Tracer resolution (2.1): absent/partial/complete/failing Langfuse config.

Resolution is cached per configuration state (compositional root): repeated
resolves reuse the cached tracer, log their state line once and build the
client at most once. Tests clear the cache per test for determinism.
"""

import logging
from collections.abc import Iterator

import pytest

from app.config import Settings
from app.observability import langfuse_adapter
from app.observability.langfuse_adapter import LangfuseTracer, resolve_tracer
from app.observability.noop import NoopTracer
from app.observability.ports import CapabilitySpan


@pytest.fixture(autouse=True)
def _fresh_resolution_cache() -> Iterator[None]:
    """Isolate the per-config resolution cache between tests."""
    langfuse_adapter._resolve_cached.cache_clear()
    yield
    langfuse_adapter._resolve_cached.cache_clear()


def _span() -> CapabilitySpan:
    return CapabilitySpan(
        entity="creative_item:test", prompt_version="consistency.text.v1",
        model="fake-text", latency_ms=1.0,
    )


def test_absent_config_resolves_noop_with_single_info_log(caplog) -> None:
    settings = Settings(_env_file=None)
    with caplog.at_level(logging.INFO, logger="app.observability.langfuse_adapter"):
        tracer = resolve_tracer(settings)
    assert isinstance(tracer, NoopTracer)
    records = [r for r in caplog.records if "Langfuse" in r.message]
    assert len(records) == 1
    assert records[0].levelno == logging.INFO


def test_partial_config_resolves_noop_naming_missing_settings_without_values(caplog) -> None:
    settings = Settings(_env_file=None, langfuse_public_key="pk-lf-secret-value")
    with caplog.at_level(logging.WARNING, logger="app.observability.langfuse_adapter"):
        tracer = resolve_tracer(settings)
    assert isinstance(tracer, NoopTracer)
    records = [r for r in caplog.records if "Langfuse" in r.message]
    assert len(records) == 1
    message = records[0].getMessage()
    assert records[0].levelno == logging.WARNING
    # Names of the missing variables, never the configured value.
    assert "CONTENT_SUITE_LANGFUSE_SECRET_KEY" in message
    assert "CONTENT_SUITE_LANGFUSE_HOST" in message
    assert "pk-lf-secret-value" not in message


def test_complete_config_resolves_the_langfuse_adapter(monkeypatch) -> None:
    sentinel = object()
    monkeypatch.setattr(
        "app.observability.langfuse_adapter._build_client",
        lambda public_key, secret_key, host, environment: sentinel,
    )
    settings = Settings(
        _env_file=None,
        langfuse_public_key="pk-lf-test",
        langfuse_secret_key="sk-lf-test",
        langfuse_host="https://langfuse.example",
    )
    tracer = resolve_tracer(settings)
    assert isinstance(tracer, LangfuseTracer)
    assert tracer._client is sentinel


def test_environment_setting_is_forwarded_to_the_client(monkeypatch) -> None:
    built: list[str] = []

    def recording_client(public_key: str, secret_key: str, host: str, environment: str) -> object:
        built.append(environment)
        return object()

    monkeypatch.setattr("app.observability.langfuse_adapter._build_client", recording_client)
    settings = Settings(
        _env_file=None,
        langfuse_public_key="pk-lf-env",
        langfuse_secret_key="sk-lf-env",
        langfuse_host="https://langfuse-env.example",
        langfuse_environment="production",
    )
    assert isinstance(resolve_tracer(settings), LangfuseTracer)
    assert built == ["production"]


def test_failed_initialization_degrades_to_noop_with_sanitized_log(monkeypatch, caplog) -> None:
    def broken_client(public_key: str, secret_key: str, host: str, environment: str) -> object:
        raise RuntimeError("sdk exploded with secret sk-lf-test")

    monkeypatch.setattr("app.observability.langfuse_adapter._build_client", broken_client)
    settings = Settings(
        _env_file=None,
        langfuse_public_key="pk-lf-test",
        langfuse_secret_key="sk-lf-test",
        langfuse_host="https://langfuse.example",
    )
    with caplog.at_level(logging.WARNING, logger="app.observability.langfuse_adapter"):
        tracer = resolve_tracer(settings)
    assert isinstance(tracer, NoopTracer)
    records = [r for r in caplog.records if "Langfuse" in r.message]
    assert len(records) == 1
    message = records[0].getMessage()
    assert "RuntimeError" in message
    assert "secret" not in message.lower()


def test_noop_tracer_emits_silently_without_network() -> None:
    import asyncio

    async def scenario() -> str | None:
        return await NoopTracer().emit_span(_span())

    assert asyncio.run(scenario()) is None


def test_repeated_absent_config_resolution_is_cached_with_single_log(caplog) -> None:
    settings = Settings(_env_file=None)
    with caplog.at_level(logging.INFO, logger="app.observability.langfuse_adapter"):
        first = resolve_tracer(settings)
        second = resolve_tracer(settings)
    assert first is second
    assert isinstance(first, NoopTracer)
    assert len([r for r in caplog.records if "Langfuse" in r.message]) == 1


def test_repeated_partial_config_resolution_logs_the_warning_once(caplog) -> None:
    settings = Settings(_env_file=None, langfuse_public_key="pk-lf-secret-value")
    with caplog.at_level(logging.WARNING, logger="app.observability.langfuse_adapter"):
        first = resolve_tracer(settings)
        second = resolve_tracer(settings)
    assert first is second
    assert isinstance(first, NoopTracer)
    assert len([r for r in caplog.records if "Langfuse" in r.message]) == 1


def test_repeated_complete_config_resolution_builds_the_client_once(monkeypatch) -> None:
    built: list[tuple[str, str, str]] = []

    def counting_client(public_key: str, secret_key: str, host: str, environment: str) -> object:
        built.append((public_key, secret_key, host))
        return object()

    monkeypatch.setattr(
        "app.observability.langfuse_adapter._build_client", counting_client
    )
    settings = Settings(
        _env_file=None,
        langfuse_public_key="pk-lf-repeat",
        langfuse_secret_key="sk-lf-repeat",
        langfuse_host="https://langfuse-repeat.example",
    )
    first = resolve_tracer(settings)
    second = resolve_tracer(settings)
    assert first is second
    assert isinstance(first, LangfuseTracer)
    assert len(built) == 1


def test_repeated_failed_initialization_degrades_with_single_log(monkeypatch, caplog) -> None:
    def broken_client(public_key: str, secret_key: str, host: str, environment: str) -> object:
        raise RuntimeError("sdk exploded")

    monkeypatch.setattr(
        "app.observability.langfuse_adapter._build_client", broken_client
    )
    settings = Settings(
        _env_file=None,
        langfuse_public_key="pk-lf-flaky",
        langfuse_secret_key="sk-lf-flaky",
        langfuse_host="https://langfuse-flaky.example",
    )
    with caplog.at_level(logging.WARNING, logger="app.observability.langfuse_adapter"):
        first = resolve_tracer(settings)
        second = resolve_tracer(settings)
    assert first is second
    assert isinstance(first, NoopTracer)
    assert len([r for r in caplog.records if "Langfuse" in r.message]) == 1
