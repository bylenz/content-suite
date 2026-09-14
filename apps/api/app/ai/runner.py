"""Capability runner (async): adapter guard -> prompt resolution -> awaited
adapter call -> Pydantic contract validation -> guarded span emission.

Adapters and the tracer arrive by dependency injection. `adapter=None` is the
only representation of an unconfigured provider and fails fast with
`AIProviderNotConfiguredError` — no silent fallback. Span emission is guarded
here (single guard root: every consumer goes through the runner), so a tracer
failure never breaks the domain operation.
"""

import logging
import time
from dataclasses import dataclass

from pydantic import ValidationError

from app.ai import prompts
from app.ai.contracts import (
    BrandDnaDocument,
    ConsistencyResult,
    CreativeOutput,
    VisualAuditResult,
    build_trace_summary,
)
from app.ai.errors import AIOutputValidationError, AIProviderNotConfiguredError
from app.ai.ports import TextModel, VisionModel
from app.observability.ports import CapabilitySpan, Tracer

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RunMetadata:
    prompt_version: str
    model: str
    trace_id: str | None
    latency_ms: float


@dataclass(frozen=True, slots=True)
class RunResult[
    ContractT: (CreativeOutput, ConsistencyResult, VisualAuditResult, BrandDnaDocument)
]:
    output: ContractT
    metadata: RunMetadata


async def run_capability[
    ContractT: (CreativeOutput, ConsistencyResult, VisualAuditResult, BrandDnaDocument)
](
    *,
    prompt_id: str,
    adapter: TextModel | VisionModel | None,
    tracer: Tracer,
    contract: type[ContractT],
    request: str,
    entity: str,
    image_ref: str | None = None,
    brand_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> RunResult[ContractT]:
    """Execute one structured capability end to end and return the validated output.

    Optional entity context (change 009) binds the emitted span to a brand and
    a domain entity for the local trace read model; callers without context
    keep the exact pre-009 behavior.
    """
    start = time.perf_counter()
    model: str | None
    try:
        if adapter is None:
            raise AIProviderNotConfiguredError(prompt_id)
        spec = prompts.resolve_prompt(prompt_id)
        model = adapter.name
        if isinstance(adapter, TextModel):
            if image_ref is not None:
                raise ValueError("image_ref is only valid with a VisionModel adapter")
            raw = await adapter.generate_structured(
                instructions=spec.template,
                prompt=request,
                response_schema=contract.model_json_schema(),
            )
        else:
            if image_ref is None:
                raise ValueError("image_ref is required with a VisionModel adapter")
            raw = await adapter.analyze_structured(
                instructions=spec.template, prompt=request, image_ref=image_ref
            )
        normalize = getattr(contract, "normalize_provider_payload", None)
        if normalize is not None and isinstance(raw, dict):
            raw = normalize(raw)
        try:
            output = contract.model_validate(raw)
        except ValidationError as exc:
            raise AIOutputValidationError(contract.__name__, exc) from exc
    except Exception as exc:
        await _emit(
            tracer,
            CapabilitySpan(
                entity=entity,
                prompt_version=prompt_id,
                model=adapter.name if adapter is not None else None,
                latency_ms=_elapsed_ms(start),
                error=type(exc).__name__,
                brand_id=brand_id,
                entity_type=entity_type,
                entity_id=entity_id,
            ),
        )
        raise
    latency_ms = _elapsed_ms(start)
    trace_id = await _emit(
        tracer,
        CapabilitySpan(
            entity=entity,
            prompt_version=spec.id,
            model=model,
            latency_ms=latency_ms,
            summary=build_trace_summary(output),
            brand_id=brand_id,
            entity_type=entity_type,
            entity_id=entity_id,
        ),
    )
    return RunResult(
        output=output,
        metadata=RunMetadata(
            prompt_version=spec.id,
            model=model if model is not None else "",
            trace_id=trace_id,
            latency_ms=latency_ms,
        ),
    )


async def _emit(tracer: Tracer, span: CapabilitySpan) -> str | None:
    """Emit one span; tracer failures degrade to a sanitized warning, never propagate."""
    try:
        return await tracer.emit_span(span)
    except Exception as exc:
        logger.warning("Tracer failed while emitting span: %s", type(exc).__name__)
        return None


def _elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0
