"""Deterministic async fakes for the ai ports: tests and local dev, no network.

Each fake records its calls so tests can assert whether a model was invoked.
Default structured payloads satisfy the CreativeOutput / VisualAuditResult
contracts; inject other payloads per scenario.
"""

import zlib
from collections.abc import Mapping, Sequence
from typing import Any

EMBEDDING_DIMENSIONS = 8


def default_creative_output() -> dict[str, Any]:
    return {
        "content_type": "product_description",
        "title": "Quinoa Bites",
        "content": "Bites de quinua horneados con ingredientes que puedes nombrar.",
        "applied_rule_ids": ["rule-tone-warm"],
    }


def default_visual_audit_result() -> dict[str, Any]:
    return {
        "checks": [{"check_id": "check-logo", "label": "Logo usage", "status": "pass"}],
        "findings": [],
        "summary": "El visual cumple las reglas obligatorias de marca.",
    }


class FakeTextModel:
    name = "fake-text-model"

    def __init__(
        self, *, text_output: str = "fake text", structured_output: dict[str, Any] | None = None
    ) -> None:
        self.text_output = text_output
        self.structured_output = (
            structured_output if structured_output is not None else default_creative_output()
        )
        self.calls: list[dict[str, Any]] = []

    async def generate(self, *, instructions: str, prompt: str) -> str:
        self.calls.append({"op": "generate", "instructions": instructions, "prompt": prompt})
        return self.text_output

    async def generate_structured(
        self, *, instructions: str, prompt: str, response_schema: Mapping[str, Any]
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "op": "generate_structured",
                "instructions": instructions,
                "prompt": prompt,
                "response_schema": response_schema,
            }
        )
        return dict(self.structured_output)


class FakeVisionModel:
    name = "fake-vision-model"

    def __init__(self, *, structured_output: dict[str, Any] | None = None) -> None:
        self.structured_output = (
            structured_output if structured_output is not None else default_visual_audit_result()
        )
        self.calls: list[dict[str, Any]] = []

    async def analyze_structured(
        self, *, instructions: str, prompt: str, image_ref: str
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "op": "analyze_structured",
                "instructions": instructions,
                "prompt": prompt,
                "image_ref": image_ref,
            }
        )
        return dict(self.structured_output)


class FakeEmbeddingModel:
    name = "fake-embedding-model"
    dimensions = EMBEDDING_DIMENSIONS

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append({"op": "embed", "texts": list(texts)})
        return [self.vector_for(text) for text in texts]

    @staticmethod
    def vector_for(text: str) -> list[float]:
        """Deterministic vector from a stable hash of the text."""
        seed = (zlib.crc32(text.encode("utf-8")) % 1000) / 1000.0
        return [seed] * EMBEDDING_DIMENSIONS
