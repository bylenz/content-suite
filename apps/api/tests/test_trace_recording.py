"""Trace recording (change 009, task 5.1): span entity-context validation,
RecordingTracer sink behavior, SQL repository roundtrip and runner pass-through.
Fakes only — no network, no Langfuse SDK."""

import asyncio
from collections.abc import Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.orm import sessionmaker

from app.ai.contracts import CreativeOutput
from app.ai.fakes import FakeTextModel
from app.ai.runner import run_capability
from app.observability.noop import NoopTracer
from app.observability.ports import CapabilitySpan, TraceQuery
from app.observability.recording import RecordingTracer
from app.observability.repository import SqlTraceRecordRepository


def run[ResultT](coro: Coroutine[Any, Any, ResultT]) -> ResultT:
    return asyncio.run(coro)


class FakeTraceRepository:
    """Deterministic in-memory sink for the TraceRecordRepository port."""

    def __init__(self, *, error: Exception | None = None) -> None:
        self.saved: list[tuple[CapabilitySpan, str | None]] = []
        self.error = error

    async def save(self, span: CapabilitySpan, trace_id: str | None) -> None:
        if self.error is not None:
            raise self.error
        self.saved.append((span, trace_id))

    async def list(self, query: TraceQuery):  # pragma: no cover - read path unused here
        raise NotImplementedError

    async def get_by_trace_id(self, trace_id: str):  # pragma: no cover - unused here
        raise NotImplementedError


class StubTracer:
    def __init__(self, trace_id: str | None = "stub-trace-1") -> None:
        self.trace_id = trace_id
        self.spans: list[CapabilitySpan] = []

    async def emit_span(self, span: CapabilitySpan) -> str | None:
        self.spans.append(span)
        return self.trace_id


def bound_span(**overrides: Any) -> CapabilitySpan:
    defaults: dict[str, Any] = {
        "entity": "creative_item:1",
        "model": "fake-text-model",
        "latency_ms": 12.5,
        "operation": "creative.generate",
        "brand_id": str(uuid4()),
        "entity_type": "creative_version",
        "entity_id": str(uuid4()),
    }
    return CapabilitySpan(**{**defaults, **overrides})


def test_span_entity_context_must_be_set_together() -> None:
    with pytest.raises(ValueError, match="entity_id and entity_type must be set together"):
        bound_span(entity_id=None)
    with pytest.raises(ValueError, match="entity_id and entity_type must be set together"):
        bound_span(entity_type=None)
    # Both present and both absent are both valid.
    assert bound_span().entity_type == "creative_version"
    legacy = CapabilitySpan(entity="e", model=None, latency_ms=1.0, operation="knowledge.sync")
    assert legacy.entity_type is None


def test_recording_tracer_saves_row_with_inner_trace_id() -> None:
    repo = FakeTraceRepository()
    inner = StubTracer(trace_id="langfuse-xyz")
    tracer = RecordingTracer(repo, inner)
    span = bound_span()
    assert run(tracer.emit_span(span)) == "langfuse-xyz"
    assert repo.saved == [(span, "langfuse-xyz")]
    assert inner.spans == [span]


def test_recording_tracer_with_noop_inner_saves_null_trace_id() -> None:
    repo = FakeTraceRepository()
    tracer = RecordingTracer(repo, NoopTracer())
    assert run(tracer.emit_span(bound_span())) is None
    assert repo.saved[0][1] is None  # spec scenario: row persists with null trace_id


def test_recording_tracer_skips_legacy_spans_without_entity_type() -> None:
    repo = FakeTraceRepository()
    inner = StubTracer()
    tracer = RecordingTracer(repo, inner)
    legacy = CapabilitySpan(
        entity="brand_knowledge:1", model=None, latency_ms=2.0, operation="knowledge.sync"
    )
    assert run(tracer.emit_span(legacy)) == "stub-trace-1"
    assert repo.saved == []
    assert inner.spans == [legacy]  # emission still delegated unchanged


def test_recording_tracer_tolerates_save_failure() -> None:
    repo = FakeTraceRepository(error=RuntimeError("db down"))
    tracer = RecordingTracer(repo, StubTracer(trace_id="kept"))
    assert run(tracer.emit_span(bound_span())) == "kept"  # trace_id never lost


def test_sql_repository_roundtrip_and_authorization_narrowing(engine) -> None:
    repo = SqlTraceRecordRepository(session_factory=sessionmaker(bind=engine))
    brand, other_brand, entity_id = uuid4(), uuid4(), uuid4()
    rows = {
        "own-ok": bound_span(
            brand_id=str(brand), entity_type="creative_version", entity_id=str(entity_id)
        ),
        "own-error": bound_span(brand_id=str(brand), error="AIOutputValidationError"),
        "foreign": bound_span(brand_id=str(other_brand)),
        "unbound": bound_span(brand_id=None),
    }
    for trace_id, span in rows.items():
        run(repo.save(span, trace_id))

    page = run(repo.list(TraceQuery(brand_ids=(str(brand),))))
    assert page.total == 2
    assert [item.trace_id for item in page.items] == ["own-error", "own-ok"]  # newest first
    assert page.items[0].outcome == "error"
    assert page.items[0].error_type == "AIOutputValidationError"
    assert page.items[1].entity_type == "creative_version"
    assert page.items[1].outcome == "ok"

    entity_page = run(
        repo.list(
            TraceQuery(
                brand_ids=(str(brand),),
                entity_type="creative_version",
                entity_id=str(entity_id),
            )
        )
    )
    assert [item.trace_id for item in entity_page.items] == ["own-ok"]

    paged = run(repo.list(TraceQuery(brand_ids=(str(brand),), limit=1, offset=1)))
    assert paged.total == 2 and len(paged.items) == 1

    # Empty authorized set -> empty page; detail lookup ignores brand scoping by
    # port contract (the service authorizes before/after the call).
    assert run(repo.list(TraceQuery(brand_ids=()))).total == 0
    own = run(repo.get_by_trace_id("own-ok"))
    assert own is not None and own.brand_id == brand
    assert run(repo.get_by_trace_id("missing")) is None


def test_sql_repository_date_range_filters(engine) -> None:
    repo = SqlTraceRecordRepository(session_factory=sessionmaker(bind=engine))
    brand = str(uuid4())
    run(repo.save(bound_span(brand_id=brand), "dated-1"))
    now = datetime.now(UTC)
    past, future = now - timedelta(hours=1), now + timedelta(hours=1)
    assert run(repo.list(TraceQuery(brand_ids=(brand,), date_from=past, date_to=future))).total == 1
    assert run(repo.list(TraceQuery(brand_ids=(brand,), date_to=past))).total == 0
    assert run(repo.list(TraceQuery(brand_ids=(brand,), date_from=future))).total == 0


def test_runner_passes_entity_context_to_tracer() -> None:
    repo = FakeTraceRepository()
    tracer = RecordingTracer(repo, NoopTracer())
    brand, entity = str(uuid4()), str(uuid4())
    result = run(
        run_capability(
            prompt_id="creative.product_description.v1",
            adapter=FakeTextModel(),
            tracer=tracer,
            contract=CreativeOutput,
            request="Escribe una descripcion para Quinoa Bites",
            entity="creative_item:1",
            brand_id=brand,
            entity_type="creative_version",
            entity_id=entity,
        )
    )
    assert result.metadata.trace_id is None  # no-op inner: null trace id by design
    ((span, trace_id),) = repo.saved
    assert trace_id is None
    assert span.brand_id == brand
    assert span.entity_type == "creative_version"
    assert span.entity_id == entity
    assert span.prompt_version == "creative.product_description.v1"
    # Legacy callers (no context) keep working and record nothing.
    repo2 = FakeTraceRepository()
    run(
        run_capability(
            prompt_id="creative.product_description.v1",
            adapter=FakeTextModel(),
            tracer=RecordingTracer(repo2, NoopTracer()),
            contract=CreativeOutput,
            request="Escribe una descripcion para Quinoa Bites",
            entity="creative_item:2",
        )
    )
    assert repo2.saved == []
