"""Optional Langfuse tracer: the only module allowed to import the langfuse SDK.

`resolve_tracer` maps settings to a tracer with four explicit states:
1. config absent  -> NoopTracer + one info log
2. config partial -> NoopTracer + one warning log naming the missing setting
   NAMES (never their values)
3. config complete -> LangfuseTracer (SDK imported lazily, inside this module)
4. initialization failure (SDK missing/broken) -> NoopTracer + sanitized warning

Resolution is cached per configuration state (compositional root): each state
line is logged and the client built at most once per process, and the cache is
thread-safe for the FastAPI runtime.

Raw input/output capture is disabled by construction: `start_observation` is
called without input/output arguments and span metadata only carries scalars
plus the bounded `TraceSummary`. Runtime SDK failures are caught inside the
adapter and logged sanitized; the domain operation always completes.
"""

import logging
from functools import cache
from typing import Any

from app.config import Settings
from app.observability.errors import TracerInitializationError
from app.observability.noop import NoopTracer
from app.observability.ports import CapabilitySpan, Tracer

logger = logging.getLogger(__name__)

_LANGFUSE_SETTINGS = ("langfuse_public_key", "langfuse_secret_key", "langfuse_host")


class LangfuseTracer:
    """Emits sanitized spans through an injected Langfuse client."""

    def __init__(self, client: Any) -> None:
        # The client is injected so tests stub the SDK without any network.
        self._client = client

    async def emit_span(self, span: CapabilitySpan) -> str | None:
        try:
            # Name invariant: operation wins when present; prompt-only spans (005)
            # keep their exact historical names.
            name = span.operation if span.operation is not None else span.prompt_version
            observation = self._client.start_observation(name=name, as_type="span")
            metadata: dict[str, Any] = {
                "entity": span.entity,
                "prompt_version": span.prompt_version,
                "model": span.model,
                "latency_ms": span.latency_ms,
                "summary": (
                    span.summary.model_dump() if span.summary is not None else None
                ),
                "error": span.error,
            }
            if span.operation is not None:
                # Only added when present so prompt-only spans keep their exact
                # metadata shape (005 contract).
                metadata["operation"] = span.operation
            observation.update(metadata=metadata)
            observation.end()
            return getattr(observation, "trace_id", None)
        except Exception as exc:
            logger.warning("Langfuse span emission failed: %s", type(exc).__name__)
            return None


def _build_client(langfuse_public_key: str, langfuse_secret_key: str, langfuse_host: str) -> Any:
    """Construct the Langfuse client with a lazy SDK import (complete config only)."""
    try:
        from langfuse import Langfuse  # lazy by design: this module is the SDK boundary
    except ImportError as exc:
        raise TracerInitializationError("langfuse SDK is not installed") from exc
    return Langfuse(
        public_key=langfuse_public_key,
        secret_key=langfuse_secret_key,
        host=langfuse_host,
    )


def resolve_tracer(settings: Settings) -> Tracer:
    """Resolve the tracer from settings (states 1-4 described in the module docstring).

    Compositional root for tracing: delegates to a `functools.cache` keyed on the
    Langfuse configuration, so resolution is thread-safe and idempotent — each
    distinct configuration state logs its single state line and builds its
    client at most once per process, however many callers resolve.
    """
    return _resolve_cached(
        settings.langfuse_public_key, settings.langfuse_secret_key, settings.langfuse_host
    )


@cache
def _resolve_cached(
    langfuse_public_key: str, langfuse_secret_key: str, langfuse_host: str
) -> Tracer:
    missing = [
        f"CONTENT_SUITE_{field.upper()}"
        for field, value in zip(
            _LANGFUSE_SETTINGS,
            (langfuse_public_key, langfuse_secret_key, langfuse_host),
            strict=True,
        )
        if not value
    ]
    if not missing:
        try:
            return LangfuseTracer(
                _build_client(langfuse_public_key, langfuse_secret_key, langfuse_host)
            )
        except Exception as exc:
            logger.warning(
                "Langfuse tracer initialization failed (%s); falling back to no-op",
                type(exc).__name__,
            )
            return NoopTracer()
    if len(missing) == len(_LANGFUSE_SETTINGS):
        logger.info("Langfuse tracing disabled: no configuration present")
    else:
        logger.warning("Langfuse tracing disabled: missing settings %s", ", ".join(missing))
    return NoopTracer()
