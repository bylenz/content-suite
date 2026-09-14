"""Fakes (4.2): deterministic, async, protocol-compatible, network-free."""

import asyncio
import inspect

from app.ai.fakes import (
    FakeEmbeddingModel,
    FakeTextModel,
    FakeVisionModel,
    default_creative_output,
    default_visual_audit_result,
)
from app.ai.ports import EmbeddingModel, TextModel, VisionModel

# Static protocol compatibility: ty rejects these assignments if any fake's method
# signature (parameter or return types) diverges from its port.
_TEXT_FAKE_IS_A_PORT: TextModel = FakeTextModel()
_VISION_FAKE_IS_A_PORT: VisionModel = FakeVisionModel()
_EMBEDDING_FAKE_IS_A_PORT: EmbeddingModel = FakeEmbeddingModel()


def test_fakes_satisfy_their_ports() -> None:
    assert isinstance(FakeTextModel(), TextModel)
    assert isinstance(FakeVisionModel(), VisionModel)
    assert isinstance(FakeEmbeddingModel(), EmbeddingModel)


def test_fake_operations_are_async() -> None:
    assert inspect.iscoroutinefunction(FakeTextModel.generate)
    assert inspect.iscoroutinefunction(FakeTextModel.generate_structured)
    assert inspect.iscoroutinefunction(FakeVisionModel.analyze_structured)
    assert inspect.iscoroutinefunction(FakeEmbeddingModel.embed)


def test_fake_text_model_is_deterministic_and_records_calls() -> None:
    fake = FakeTextModel()

    async def scenario() -> tuple[str, dict, str, dict]:
        return (
            await fake.generate(instructions="i", prompt="p"),
            await fake.generate_structured(instructions="i", prompt="p", response_schema={}),
            (await FakeTextModel().generate(instructions="i", prompt="p")),
            (
                await FakeTextModel().generate_structured(
                    instructions="i", prompt="p", response_schema={}
                )
            ),
        )

    first_text, first_structured, repeat_text, repeat_structured = asyncio.run(scenario())
    assert first_text == repeat_text
    assert first_structured == repeat_structured
    assert first_structured == default_creative_output()
    assert len(fake.calls) == 2
    assert fake.calls[1]["op"] == "generate_structured"


def test_fake_vision_model_defaults_and_custom_payloads() -> None:
    fake = FakeVisionModel()

    async def scenario() -> dict:
        return await fake.analyze_structured(
            instructions="audit rules", prompt="check this", image_ref="storage://a.png"
        )

    assert asyncio.run(scenario()) == default_visual_audit_result()
    custom = FakeVisionModel(structured_output={"unexpected": True})
    assert custom.structured_output == {"unexpected": True}  # injectable for failure tests


def test_fake_embedding_model_is_deterministic_per_text() -> None:
    fake = FakeEmbeddingModel()

    async def scenario() -> list[list[float]]:
        return await fake.embed(["hola", "hola", "otro"])

    vectors = asyncio.run(scenario())
    assert vectors[0] == vectors[1]
    assert vectors[0] != vectors[2]
    assert len(vectors[0]) == 8
    assert fake.calls[0]["texts"] == ["hola", "hola", "otro"]


def test_fake_embedding_model_accepts_any_str_sequence_like_the_port() -> None:
    fake = FakeEmbeddingModel()

    async def scenario() -> list[list[float]]:
        return await fake.embed(("hola", "otro"))  # tuple is a Sequence, not a list

    vectors = asyncio.run(scenario())
    assert len(vectors) == 2
    assert fake.calls[0]["texts"] == ["hola", "otro"]
