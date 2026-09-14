"""Ports (1.1): async fakes satisfy each protocol and await like coroutines."""

import asyncio
import inspect
from collections.abc import Mapping, Sequence
from typing import Any

from app.ai.ports import EmbeddingModel, TextModel, VisionModel


class FakeForTestText:
    name = "fake-text"

    async def generate(self, *, instructions: str, prompt: str) -> str:
        return f"{instructions}|{prompt}"

    async def generate_structured(
        self, *, instructions: str, prompt: str, response_schema: Mapping[str, Any]
    ) -> dict[str, Any]:
        return {
            "instructions": instructions,
            "prompt": prompt,
            "schema_keys": list(response_schema),
        }


class FakeForTestVision:
    name = "fake-vision"

    async def analyze_structured(
        self, *, instructions: str, prompt: str, image_ref: str
    ) -> dict[str, Any]:
        return {"image_ref": image_ref, "prompt": prompt}


class FakeForTestEmbedding:
    name = "fake-embedding"
    dimensions = 1

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[float(len(text))] for text in texts]


# Static protocol proof (checked by `uv run ty check`): the fake is structurally
# assignable to the port, so the `Sequence[str]` parameter variance is enforced
# statically — `list[str]` here would fail the assignment, and runtime
# `isinstance` alone would not notice.
_embedding_model: EmbeddingModel = FakeForTestEmbedding()


def test_async_fake_satisfies_each_port() -> None:
    assert isinstance(FakeForTestText(), TextModel)
    assert isinstance(FakeForTestVision(), VisionModel)
    assert isinstance(FakeForTestEmbedding(), EmbeddingModel)


def test_port_operations_are_async_coroutines() -> None:
    text, vision, embedding = FakeForTestText(), FakeForTestVision(), FakeForTestEmbedding()
    assert inspect.iscoroutinefunction(text.generate)
    assert inspect.iscoroutinefunction(text.generate_structured)
    assert inspect.iscoroutinefunction(vision.analyze_structured)
    assert inspect.iscoroutinefunction(embedding.embed)


def test_awaited_calls_return_expected_values() -> None:
    async def scenario() -> tuple[str, dict[str, Any], list[list[float]]]:
        return (
            await FakeForTestText().generate(instructions="i", prompt="p"),
            await FakeForTestVision().analyze_structured(
                instructions="i", prompt="p", image_ref="assets/a.png"
            ),
            await FakeForTestEmbedding().embed(["hola", "adios"]),
        )

    text_out, vision_out, embeddings = asyncio.run(scenario())
    assert text_out == "i|p"
    assert vision_out == {"image_ref": "assets/a.png", "prompt": "p"}
    assert embeddings == [[4.0], [5.0]]


def test_an_object_missing_operations_does_not_satisfy_a_port() -> None:
    class NotAModel:
        name = "incomplete"

    assert not isinstance(NotAModel(), TextModel)
    assert not isinstance(NotAModel(), VisionModel)
    assert not isinstance(NotAModel(), EmbeddingModel)
