"""Runner (4.1): prompt -> awaited adapter -> contract -> sanitized span."""

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

import pytest

from app.ai.contracts import ConsistencyResult, CreativeOutput, TraceSummary, VisualAuditResult
from app.ai.errors import (
    AIOutputValidationError,
    AIPromptNotFoundError,
    AIProviderNotConfiguredError,
)
from app.ai.fakes import FakeTextModel, FakeVisionModel
from app.ai.runner import RunResult, run_capability
from app.observability.noop import NoopTracer
from app.observability.ports import CapabilitySpan

CREATIVE_CONTRACT_PAYLOAD = {
    "content_type": "product_description",
    "title": "Quinoa Bites",
    "content": "Bites de quinua horneados con ingredientes reales.",
    "applied_rule_ids": ["rule-tone-warm"],
}


class RecordingTracer:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.spans: list[CapabilitySpan] = []
        self.error = error

    async def emit_span(self, span: CapabilitySpan) -> str | None:
        self.spans.append(span)
        if self.error is not None:
            raise self.error
        return "trace-recorded"


def run[ResultT](coro: Coroutine[Any, Any, ResultT]) -> ResultT:
    """Typed wrapper: preserves the awaited type so `RunResult[ContractT]`
    assertions are checked for real and can never pass via `Any`."""
    return asyncio.run(coro)


def test_happy_path_returns_validated_output_and_metadata() -> None:
    tracer = RecordingTracer()
    result = run(
        run_capability(
            prompt_id="creative.product_description.v1",
            adapter=FakeTextModel(),
            tracer=tracer,
            contract=CreativeOutput,
            request="Escribe una descripcion para Quinoa Bites",
            entity="creative_item:123",
        )
    )
    assert isinstance(result.output, CreativeOutput)
    assert result.output.title == "Quinoa Bites"
    assert result.metadata.prompt_version == "creative.product_description.v1"
    assert result.metadata.model == "fake-text-model"
    assert result.metadata.trace_id == "trace-recorded"
    assert result.metadata.latency_ms >= 0.0


def test_success_span_carries_only_bounded_summary() -> None:
    tracer = RecordingTracer()
    run(
        run_capability(
            prompt_id="creative.product_description.v1",
            adapter=FakeTextModel(),
            tracer=tracer,
            contract=CreativeOutput,
            request="request text",
            entity="creative_item:123",
        )
    )
    assert len(tracer.spans) == 1
    span = tracer.spans[0]
    assert span.error is None
    assert isinstance(span.summary, TraceSummary)
    assert span.summary.model_dump() == {
        "contract": "CreativeOutput",
        "ok": True,
        "content_type": "product_description",
        "check_count": 0,
        "finding_count": 0,
    }
    # The span payload has no free-text fields that could carry the raw request.
    assert "request text" not in span.summary.model_dump_json()


def test_malformed_output_raises_explicit_contract_error_and_error_span() -> None:
    tracer = RecordingTracer()
    broken = dict(CREATIVE_CONTRACT_PAYLOAD)
    broken.pop("title")
    with pytest.raises(AIOutputValidationError) as excinfo:
        run(
            run_capability(
                prompt_id="creative.product_description.v1",
                adapter=FakeTextModel(structured_output=broken),
                tracer=tracer,
                contract=CreativeOutput,
                request="request",
                entity="creative_item:123",
            )
        )
    assert excinfo.value.contract == "CreativeOutput"
    assert len(tracer.spans) == 1
    span = tracer.spans[0]
    assert span.error == "AIOutputValidationError"
    assert span.summary is None


def test_missing_provider_fails_fast_without_fallback() -> None:
    tracer = RecordingTracer()
    with pytest.raises(AIProviderNotConfiguredError):
        run(
            run_capability(
                prompt_id="consistency.text.v1",
                adapter=None,
                tracer=tracer,
                contract=ConsistencyResult,
                request="request",
                entity="creative_item:123",
            )
        )
    assert len(tracer.spans) == 1
    assert tracer.spans[0].error == "AIProviderNotConfiguredError"
    assert tracer.spans[0].model is None


def test_unknown_prompt_fails_without_invoking_the_model() -> None:
    tracer = RecordingTracer()
    fake = FakeTextModel()
    with pytest.raises(AIPromptNotFoundError):
        run(
            run_capability(
                prompt_id="creative.product_description.v9",
                adapter=fake,
                tracer=tracer,
                contract=CreativeOutput,
                request="request",
                entity="creative_item:123",
            )
        )
    assert fake.calls == []
    assert tracer.spans[0].error == "AIPromptNotFoundError"


def test_vision_capability_uses_analyze_structured_with_image_ref() -> None:
    tracer = RecordingTracer()
    vision = FakeVisionModel()
    # Static proof of RunResult[ContractT]: this annotation only type-checks while
    # the generic preserves the selected output contract.
    result: RunResult[VisualAuditResult] = run(
        run_capability(
            prompt_id="audit.visual.v1",
            adapter=vision,
            tracer=tracer,
            contract=VisualAuditResult,
            request="Audita el visual contra las reglas",
            entity="visual_asset:abc",
            image_ref="storage://visuals/abc-v1.png",
        )
    )
    assert isinstance(result.output, VisualAuditResult)
    assert vision.calls[0]["image_ref"] == "storage://visuals/abc-v1.png"
    assert tracer.spans[0].summary is not None
    assert tracer.spans[0].summary.check_count == 1


def test_text_capability_rejects_image_ref_and_vision_requires_it() -> None:
    with pytest.raises(ValueError):
        run(
            run_capability(
                prompt_id="creative.product_description.v1",
                adapter=FakeTextModel(),
                tracer=RecordingTracer(),
                contract=CreativeOutput,
                request="request",
                entity="creative_item:1",
                image_ref="storage://x.png",
            )
        )
    with pytest.raises(ValueError):
        run(
            run_capability(
                prompt_id="audit.visual.v1",
                adapter=FakeVisionModel(),
                tracer=RecordingTracer(),
                contract=VisualAuditResult,
                request="request",
                entity="visual_asset:1",
            )
        )


def test_tracer_failure_never_breaks_the_domain_operation(caplog) -> None:
    tracer = RecordingTracer(error=RuntimeError("tracer exploded"))
    with caplog.at_level(logging.WARNING, logger="app.ai.runner"):
        result = run(
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
    assert any("RuntimeError" in r.message for r in caplog.records)


def test_noop_tracer_integration_returns_none_trace_id() -> None:
    result = run(
        run_capability(
            prompt_id="creative.product_description.v1",
            adapter=FakeTextModel(),
            tracer=NoopTracer(),
            contract=CreativeOutput,
            request="request",
            entity="creative_item:123",
        )
    )
    assert result.metadata.trace_id is None


def test_runner_normalizes_provider_payload_that_fills_both_bodies() -> None:
    """Strict-mode providers may fill both bodies; the runner keeps structured_sections."""
    both = {
        "content_type": "video_script",
        "title": "Reel",
        "content": "[INTRO] flattened script",
        "structured_sections": [{"heading": "Intro", "body": "Taza humeante"}],
        "applied_rule_ids": ["r1"],
    }
    result = asyncio.run(
        run_capability(
            prompt_id="creative.video_script.v1",
            adapter=FakeTextModel(structured_output=both),
            tracer=NoopTracer(),
            contract=CreativeOutput,
            request="brief",
            entity="creative_item:x",
        )
    )
    assert result.output.content is None
    assert result.output.structured_sections is not None
