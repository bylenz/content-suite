"""Startup integration (6.3): unconfigured provider/Langfuse.

The API starts without tracing errors, and an internal (non-HTTP) capability
invocation fails with the controlled `AIProviderNotConfiguredError` while logs
stay free of payloads and secrets.
"""

import asyncio
import logging

import pytest
from fastapi.testclient import TestClient

from app.ai.contracts import ConsistencyResult
from app.ai.errors import AIProviderNotConfiguredError
from app.ai.runner import run_capability
from app.config import Settings
from app.main import app
from app.observability.langfuse_adapter import resolve_tracer
from app.observability.noop import NoopTracer


def test_api_starts_without_tracing_errors_and_serves_health() -> None:
    with TestClient(app) as client:
        assert client.get("/health/live").json() == {"status": "live"}


def test_tracer_resolution_is_noop_when_environment_is_unconfigured() -> None:
    assert isinstance(resolve_tracer(Settings(_env_file=None)), NoopTracer)


def test_internal_capability_call_fails_controlled_without_fallback(caplog) -> None:
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(AIProviderNotConfiguredError) as excinfo:
            asyncio.run(
                run_capability(
                    prompt_id="consistency.text.v1",
                    adapter=None,  # provider resolution yields None while unconfigured
                    tracer=resolve_tracer(Settings(_env_file=None)),
                    contract=ConsistencyResult,
                    request="contenido confidencial del creator",
                    entity="creative_item:integration",
                )
            )
    assert excinfo.value.prompt_id == "consistency.text.v1"
    # No log carries the request payload or any secret-looking value.
    for record in caplog.records:
        assert "contenido confidencial" not in record.getMessage()
