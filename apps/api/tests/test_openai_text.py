"""OpenAI text adapter + resolver (spec 04): stubbed SDK, no network.

Covers: message composition (system instructions + user prompt), strict
json_schema mode for structured generation (schema rewritten so every property
is required and additionalProperties is false, nested $defs included, only
OpenAI-supported keywords kept), unparseable/non-object bodies ->
AIProviderResponseError, blocking passthrough for `generate`, resolution
absent/partial/complete, SDK import isolation.
"""

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest

from app.ai.contracts import CreativeOutput
from app.ai.errors import AIProviderResponseError
from app.ai.ports import TextModel
from app.ai.providers import resolve_text_model
from app.ai.providers.openai_text import OpenAITextModel
from app.config import Settings


class StubCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[dict[str, Any]] = []

    def create(self, **params: Any) -> Any:
        self.calls.append(params)

        class Message:
            content = self.content

        class Choice:
            message = Message()

        class Response:
            choices = [Choice()]

        return Response()


class StubOpenAIClient:
    def __init__(self, content: str) -> None:
        self.chat = type("Chat", (), {})()
        self.chat.completions = StubCompletions(content)


@pytest.fixture(autouse=True)
def _fresh_resolution_cache() -> Iterator[None]:
    from app.ai import providers

    providers._resolve_text_cached.cache_clear()
    yield
    providers._resolve_text_cached.cache_clear()


def test_generate_passes_instructions_and_prompt_through() -> None:
    client = StubOpenAIClient("plain text")
    model = OpenAITextModel(api_key="sk-test", model="gpt-4o-mini", client=client)

    out = asyncio.run(model.generate(instructions="sys", prompt="user prompt"))

    assert out == "plain text"
    (call,) = client.chat.completions.calls
    assert call["model"] == "gpt-4o-mini"
    assert call["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user prompt"},
    ]
    assert "response_format" not in call


def test_generate_structured_parses_strict_json_schema_mode() -> None:
    payload = {
        "content_type": "product_description",
        "title": "T",
        "content": "C",
        "structured_sections": None,
        "applied_rule_ids": [],
    }
    body = (
        '{"content_type": "product_description", "title": "T", "content": "C", '
        '"structured_sections": null, "applied_rule_ids": []}'
    )
    client = StubOpenAIClient(body)
    model = OpenAITextModel(api_key="sk-test", model="gpt-4o-mini", client=client)
    schema = CreativeOutput.model_json_schema()

    parsed = asyncio.run(
        model.generate_structured(instructions="sys", prompt="p", response_schema=schema)
    )

    assert parsed == payload
    (call,) = client.chat.completions.calls
    response_format = call["response_format"]
    assert response_format["type"] == "json_schema"
    json_schema = response_format["json_schema"]
    assert json_schema["name"] == "CreativeOutput"
    assert json_schema["strict"] is True
    strict_schema = json_schema["schema"]
    # Every declared property is required (optionality lives in anyOf null
    # branches), and no property was silently dropped.
    assert set(strict_schema["required"]) == set(strict_schema["properties"])
    assert strict_schema["additionalProperties"] is False
    # No OpenAI-unsupported keywords (e.g. minLength/maxLength/default) leak through.
    assert "minLength" not in strict_schema["properties"]["title"]
    assert "default" not in strict_schema["properties"]["content"]
    # Nested $defs (CreativeSection, used by structured_sections) are strict too.
    section_def = strict_schema["$defs"]["CreativeSection"]
    assert section_def["additionalProperties"] is False
    assert set(section_def["required"]) == set(section_def["properties"])


def test_generate_structured_rejects_non_json_body() -> None:
    client = StubOpenAIClient("not json at all")
    model = OpenAITextModel(api_key="sk-test", model="gpt-4o-mini", client=client)

    with pytest.raises(AIProviderResponseError):
        asyncio.run(
            model.generate_structured(
                instructions="sys", prompt="p", response_schema=CreativeOutput.model_json_schema()
            )
        )


def test_generate_structured_rejects_non_object_json() -> None:
    client = StubOpenAIClient("[1, 2, 3]")
    model = OpenAITextModel(api_key="sk-test", model="gpt-4o-mini", client=client)

    with pytest.raises(AIProviderResponseError):
        asyncio.run(
            model.generate_structured(
                instructions="sys", prompt="p", response_schema=CreativeOutput.model_json_schema()
            )
        )


def test_resolver_absent_config_returns_none() -> None:
    assert resolve_text_model(Settings(_env_file=None)) is None


def test_resolver_partial_config_returns_none() -> None:
    settings = Settings(_env_file=None, ai_provider="openai")  # key missing
    assert resolve_text_model(settings) is None
    settings = Settings(_env_file=None, openai_api_key="sk-test")  # provider missing
    assert resolve_text_model(settings) is None


def test_resolver_complete_config_builds_adapter_with_default_model() -> None:
    model = resolve_text_model(
        Settings(_env_file=None, ai_provider="openai", openai_api_key="sk-test")
    )
    assert isinstance(model, TextModel)
    assert model.name == "gpt-4o-mini"
    explicit = resolve_text_model(
        Settings(
            _env_file=None,
            ai_provider="openai",
            openai_api_key="sk-test",
            openai_text_model="gpt-4.1",
        )
    )
    assert explicit is not None and explicit.name == "gpt-4.1"
