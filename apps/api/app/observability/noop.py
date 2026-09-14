"""No-op tracer: explicit, silent and network-free. Used when Langfuse config is
absent, partial, or its initialization failed."""

from app.observability.ports import CapabilitySpan


class NoopTracer:
    async def emit_span(self, span: CapabilitySpan) -> str | None:
        return None
