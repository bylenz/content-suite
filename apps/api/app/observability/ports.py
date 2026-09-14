"""Tracing port: one sanitized span per capability execution.

`TraceSummary` is defined in `app.ai.contracts` (canonical contract per
design.md) and imported here so the span payload stays bounded by the same
allowlist everywhere. Spans carry only scalar metadata — never raw prompts,
responses, tokens or secrets — and never change domain state.

The facade read path is a separate port (`TraceRecordRepository`): it serves
sanitized rows from the local read model and never emits spans itself (no
recursion).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.ai.contracts import TraceSummary
from app.observability.schemas import TraceRecord


@dataclass(frozen=True, slots=True)
class CapabilitySpan:
    """Sanitized metadata for one capability execution.

    Name invariant: at least one of `operation`/`prompt_version` must be
    present — an anonymous span is a construction error, never silent.

    Entity context (change 009): `brand_id`/`entity_type`/`entity_id` are
    optional scalar strings that bind the span to a domain entity for the
    local trace read model. `entity_id` and `entity_type` are exclusive-neither:
    both must be present or both absent. Legacy spans without `entity_type`
    are still emitted to the tracer but are not recorded locally (see
    `RecordingTracer`).
    """

    entity: str
    model: str | None
    latency_ms: float
    prompt_version: str | None = None
    operation: str | None = None
    summary: TraceSummary | None = None
    error: str | None = None
    brand_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None

    def __post_init__(self) -> None:
        if not self.operation and not self.prompt_version:
            raise ValueError("CapabilitySpan requires an operation or a prompt_version")
        if (self.entity_id is None) != (self.entity_type is None):
            raise ValueError("CapabilitySpan entity_id and entity_type must be set together")


@runtime_checkable
class Tracer(Protocol):
    """Emits one span per capability; returns a trace id when a real tracer is active."""

    async def emit_span(self, span: CapabilitySpan) -> str | None: ...


@dataclass(frozen=True, slots=True)
class TraceQuery:
    """Allowlisted read query for the trace read model.

    `brand_ids` carries the ALREADY authorized brands (membership resolved in
    the service before any repository call); the repository only narrows
    within it. Rows without a brand binding never match.
    """

    brand_ids: tuple[str, ...]
    entity_type: str | None = None
    entity_id: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True, slots=True)
class TracePage:
    """One page of sanitized trace records plus the total before pagination."""

    items: tuple[TraceRecord, ...]
    total: int


@runtime_checkable
class TraceRecordRepository(Protocol):
    """Read/write port over the sanitized local trace index.

    `save` persists one allowlisted row per recorded span (write failures are
    tolerated by the caller, never breaking domain operations); `list` and
    `get_by_trace_id` serve the facade. Rows carry scalars only — never raw
    prompts, responses, tokens or secrets.
    """

    async def save(self, span: CapabilitySpan, trace_id: str | None) -> None: ...

    async def list(self, query: TraceQuery) -> TracePage: ...

    async def get_by_trace_id(self, trace_id: str) -> TraceRecord | None: ...
