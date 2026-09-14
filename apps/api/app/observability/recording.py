"""Recording tracer (change 009): local read-model sink wrapped around any tracer.

Composition-root decorator: emits the span to the inner (no-op or Langfuse)
tracer FIRST, then persists one sanitized row with the returned trace id.
Write failures are tolerated with a sanitized warning (exception class name
only) — the domain operation that emitted the span always continues.

Recording rule (documented decision, task 2.2): only spans carrying entity
context (`entity_type` + `entity_id`) are recorded. Legacy spans without it
(knowledge sync/embed from change 006) are emitted but not recorded: the read
model requires an entity binding by schema, and backfilling context for them
belongs to their own changes. Facade reads never route through this tracer, so
no read is ever recorded (no recursion).
"""

import logging

from app.observability.ports import CapabilitySpan, Tracer, TraceRecordRepository

logger = logging.getLogger(__name__)


class RecordingTracer:
    """Persists one sanitized row per entity-bound span, then delegates emission."""

    def __init__(self, repository: TraceRecordRepository, inner: Tracer) -> None:
        self._repository = repository
        self._inner = inner

    async def emit_span(self, span: CapabilitySpan) -> str | None:
        trace_id = await self._inner.emit_span(span)
        if span.entity_type is None:
            logger.debug("Span without entity context not recorded: %s", span.entity)
            return trace_id
        try:
            await self._repository.save(span, trace_id)
        except Exception as exc:
            logger.warning("Trace index write failed: %s", type(exc).__name__)
        return trace_id
