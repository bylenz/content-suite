"""Prompt registry (3.2): the six versioned ids resolve; unknown ids fail before
any model call; the registry is immutable."""

import dataclasses
from typing import Any

import pytest

from app.ai.errors import AIPromptNotFoundError
from app.ai.prompts import _PROMPTS, PromptSpec, registered_prompt_ids, resolve_prompt

EXPECTED_IDS = (
    "brand.architect.v1",
    "creative.product_description.v1",
    "creative.video_script.v1",
    "creative.image_prompt.v1",
    "consistency.text.v1",
    "audit.visual.v1",
)


def test_registry_contains_exactly_the_six_initial_ids() -> None:
    assert registered_prompt_ids() == EXPECTED_IDS


def test_resolving_a_registered_prompt_returns_versioned_template() -> None:
    spec = resolve_prompt("creative.product_description.v1")
    assert isinstance(spec, PromptSpec)
    assert spec.id == "creative.product_description.v1"
    assert spec.version == "v1"
    assert spec.template  # templates are non-empty instructions


def test_unknown_prompt_id_raises_without_calling_any_model() -> None:
    with pytest.raises(AIPromptNotFoundError) as excinfo:
        resolve_prompt("creative.product_description.v99")
    assert "creative.product_description.v99" in str(excinfo.value)


def test_registry_is_immutable() -> None:
    registry: Any = _PROMPTS
    with pytest.raises(TypeError):
        registry["creative.new.v1"] = PromptSpec(name="creative.new", version="v1", template="x")
    with pytest.raises(TypeError):
        del registry["brand.architect.v1"]


def test_prompt_spec_is_frozen() -> None:
    spec = resolve_prompt("audit.visual.v1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(spec, "template", "tampered")  # noqa: B010 — ty rejects direct frozen assignment
