"""OpenAI embedding adapter: the only file allowed to import the openai SDK.

Implements the async `EmbeddingModel` port with `name`/`dimensions` declared
from configuration (no provider call). Blocking SDK calls are wrapped with
`asyncio.to_thread`; the SDK import is lazy (constructor) so importing this
package without the SDK installed never fails at import time. The SDK client is
injectable so tests stub it without any network.
"""

import asyncio
from collections.abc import Sequence
from typing import Any

DEFAULT_MODEL = "text-embedding-3-small"

# Documented default dimensions (OpenAI docs; verified via Context7 in task 3.1).
DOCUMENTED_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


def supports_custom_dimensions(model: str) -> bool:
    """Only text-embedding-3-* accepts the `dimensions` request parameter."""
    return model.startswith("text-embedding-3")


class OpenAIEmbeddingModel:
    """Async embeddings via the blocking SDK client wrapped in `asyncio.to_thread`."""

    def __init__(self, *, api_key: str, model: str, dimensions: int, client: Any = None) -> None:
        if client is None:
            from openai import OpenAI  # lazy by design: this module is the SDK boundary

            client = OpenAI(api_key=api_key)
        self._client = client
        self.name = model
        self.dimensions = dimensions
        self._supports_custom_dimensions = supports_custom_dimensions(model)

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._embed_blocking, list(texts))

    def _embed_blocking(self, texts: list[str]) -> list[list[float]]:
        params: dict[str, Any] = {"input": texts, "model": self.name}
        if self._supports_custom_dimensions:
            params["dimensions"] = self.dimensions
        response = self._client.embeddings.create(**params)
        # `index` preserves the input ordering; sort defensively anyway.
        ordered = sorted(response.data, key=lambda item: item.index)
        return [list(item.embedding) for item in ordered]
