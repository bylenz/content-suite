"""Langfuse adapter (5.2): stubbed SDK, no network.

Covers: sanitized span emission (no input/output capture), runtime SDK failure
degradation, and the full `runner -> LangfuseTracer` integration completing the
domain operation when the tracer fails. Config-state resolution (absent/
partial/complete/init-failure) lives in test_observability_tracer.py.
"""

import asyncio
import logging
from typing import Any

from app.ai.contracts import CreativeOutput
from app.ai.fakes import FakeTextModel
from app.ai.runner import run_capability
from app.observability.langfuse_adapter import LangfuseTracer
from app.observability.ports import CapabilitySpan


class StubObservation:
    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []
        self.ended = False
        self.trace_id = "trace-stub-123"

    def update(self, **kwargs: Any) -> None:
        self.updates.append(kwargs)

    def end(self) -> None:
        self.ended = True


class StubLangfuseClient:
    """Records start_observation kwargs and keeps the last observation."""

    def __init__(self, *, fail: bool = False) -> None:
        self.started: list[dict[str, Any]] = []
        self.last_observation: StubObservation | None = None
        self.fail = fail

    def start_observation(self, **kwargs: Any) -> StubObservation:
        self.started.append(kwargs)
        if self.fail:
            raise RuntimeError("sdk exploded")
        self.last_observation = StubObservation()
        return self.last_observation


def _span() -> CapabilitySpan:
    return CapabilitySpan(
        entity="creative_item:123",
        prompt_version="consistency.text.v1",
        model="fake-text-model",
        latency_ms=12.5,
    )


def test_emits_sanitized_span_without_input_output_capture() -> None:
    client = StubLangfuseClient()
    tracer = LangfuseTracer(client)

    trace_id = asyncio.run(tracer.emit_span(_span()))

    assert trace_id == "trace-stub-123"
    assert client.last_observation is not None and client.last_observation.ended
    call = client.started[0]
    assert call["name"] == "consistency.text.v1"
    assert call["as_type"] == "span"
    # Raw payload capture is disabled by construction.
    assert "input" not in call
    assert "output" not in call


def test_metadata_only_contains_allowlisted_scalars() -> None:
    client = StubLangfuseClient()
    tracer = LangfuseTracer(client)

    asyncio.run(tracer.emit_span(_span()))

    assert client.last_observation is not None
    metadata = client.last_observation.updates[0]["metadata"]
    assert set(metadata) == {
        "entity", "prompt_version", "model", "latency_ms", "summary", "error",
    }
    assert metadata["summary"] is None  # error-only span in this fixture
    assert metadata["error"] is None
    assert metadata["entity"] == "creative_item:123"
    assert metadata["latency_ms"] == 12.5


def test_runtime_sdk_failure_degrades_sanitized_and_returns_none(caplog) -> None:
    tracer = LangfuseTracer(StubLangfuseClient(fail=True))
    with caplog.at_level(logging.WARNING, logger="app.observability.langfuse_adapter"):
        trace_id = asyncio.run(tracer.emit_span(_span()))
    assert trace_id is None
    records = [r for r in caplog.records if "Langfuse" in r.message]
    assert len(records) == 1
    assert "RuntimeError" in records[0].message
    assert "exploded" not in records[0].message  # no SDK message content


def test_runner_operation_completes_when_the_real_tracer_fails() -> None:
    tracer = LangfuseTracer(StubLangfuseClient(fail=True))
    result = asyncio.run(
        run_capability(
            prompt_id="creative.product_description.v1",
            adapter=FakeTextModel(),
            tracer=tracer,
            contract=CreativeOutput,
            request="request",
            entity="creative_item:123",
        )
    )
    assert isinstance(result.output, CreativeOutput)
    assert result.metadata.trace_id is None


def test_runner_operation_emits_summary_through_the_adapter() -> None:
    client = StubLangfuseClient()
    result = asyncio.run(
        run_capability(
            prompt_id="creative.product_description.v1",
            adapter=FakeTextModel(),
            tracer=LangfuseTracer(client),
            contract=CreativeOutput,
            request="request",
            entity="creative_item:123",
        )
    )
    assert result.metadata.trace_id == "trace-stub-123"
    assert client.started[0]["name"] == "creative.product_description.v1"
    assert client.last_observation is not None
    metadata = client.last_observation.updates[0]["metadata"]
    assert metadata["summary"]["contract"] == "CreativeOutput"
    assert metadata["summary"]["content_type"] == "product_description"
    assert client.last_observation.ended
