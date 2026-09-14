"""Provider-agnostic model ports (AI_SYSTEM.md).

Every operation is async: consumers always await coroutines and each adapter
decides how to wrap its SDK (e.g. asyncio.to_thread for blocking clients).
Provider SDKs may only be imported inside `ai/providers/` adapters.
"""

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TextModel(Protocol):
    """Text generation port: free text and structured (JSON) generation."""

    name: str

    async def generate(self, *, instructions: str, prompt: str) -> str: ...

    async def generate_structured(
        self, *, instructions: str, prompt: str, response_schema: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Generate JSON constrained to `response_schema` (a Pydantic `model_json_schema()`).

        Adapters that support provider-side schema enforcement (e.g. OpenAI's
        strict `json_schema` response format) must use it instead of loose JSON
        mode: the caller's contract validation is a safety net, not the primary
        guarantee that the shape matches.
        """
        ...


@runtime_checkable
class VisionModel(Protocol):
    """Multimodal analysis port over an image reference (e.g. storage path/URL)."""

    name: str

    async def analyze_structured(
        self, *, instructions: str, prompt: str, image_ref: str
    ) -> dict[str, Any]: ...


@runtime_checkable
class EmbeddingModel(Protocol):
    """Embedding port for semantic retrieval.

    `dimensions` is declared by each adapter from its own configuration, with no
    provider call: it makes the expected model/dimension available to the sync
    claim and retrieval compatibility checks before any `await`.
    """

    name: str
    dimensions: int

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...
