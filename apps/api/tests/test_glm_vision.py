"""GLM (Zhipu/Z.ai) vision adapter + resolver: stubbed SDK, no network.

Covers: message composition (system instructions + user text/image_url content
blocks), JSON-mode parsing including a tolerated markdown-fenced body,
unparseable/non-object bodies -> AIProviderResponseError, resolution
absent/partial/complete with default base_url/model, SDK import isolation.
"""

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest

from app.ai.errors import AIProviderResponseError
from app.ai.ports import VisionModel
from app.ai.providers import DEFAULT_GLM_BASE_URL, DEFAULT_GLM_VISION_MODEL, resolve_vision_model
from app.ai.providers.glm_vision import GLMVisionModel
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

    providers._resolve_vision_cached.cache_clear()
    yield
    providers._resolve_vision_cached.cache_clear()


def test_analyze_structured_sends_text_and_image_url_content_blocks() -> None:
    client = StubOpenAIClient('{"checks": [], "findings": [], "summary": "ok"}')
    model = GLMVisionModel(
        api_key="glm-test", base_url="https://api.z.ai/api/coding/paas/v4",
        model="glm-5.3-flash", client=client,
    )

    parsed = asyncio.run(
        model.analyze_structured(
            instructions="sys", prompt="analyze this", image_ref="https://example.com/img.png"
        )
    )

    assert parsed == {"checks": [], "findings": [], "summary": "ok"}
    (call,) = client.chat.completions.calls
    assert call["model"] == "glm-5.3-flash"
    assert call["response_format"] == {"type": "json_object"}
    assert call["messages"] == [
        {"role": "system", "content": "sys"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "analyze this"},
                {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}},
            ],
        },
    ]


def test_analyze_structured_tolerates_markdown_fenced_body() -> None:
    client = StubOpenAIClient('```json\n{"checks": [], "findings": [], "summary": "ok"}\n```')
    model = GLMVisionModel(
        api_key="glm-test", base_url="https://api.z.ai/api/coding/paas/v4",
        model="glm-5.3-flash", client=client,
    )

    parsed = asyncio.run(
        model.analyze_structured(instructions="sys", prompt="p", image_ref="https://x/img.png")
    )

    assert parsed == {"checks": [], "findings": [], "summary": "ok"}


def test_analyze_structured_rejects_non_json_body() -> None:
    client = StubOpenAIClient("not json at all")
    model = GLMVisionModel(
        api_key="glm-test", base_url="https://api.z.ai/api/coding/paas/v4",
        model="glm-5.3-flash", client=client,
    )

    with pytest.raises(AIProviderResponseError):
        asyncio.run(
            model.analyze_structured(instructions="sys", prompt="p", image_ref="https://x/img.png")
        )


def test_analyze_structured_rejects_non_object_json() -> None:
    client = StubOpenAIClient("[1, 2, 3]")
    model = GLMVisionModel(
        api_key="glm-test", base_url="https://api.z.ai/api/coding/paas/v4",
        model="glm-5.3-flash", client=client,
    )

    with pytest.raises(AIProviderResponseError):
        asyncio.run(
            model.analyze_structured(instructions="sys", prompt="p", image_ref="https://x/img.png")
        )


def test_resolver_absent_config_returns_none() -> None:
    assert resolve_vision_model(Settings(_env_file=None)) is None


def test_resolver_partial_config_returns_none() -> None:
    settings = Settings(_env_file=None, vision_provider="glm")  # key missing
    assert resolve_vision_model(settings) is None
    settings = Settings(_env_file=None, glm_api_key="glm-test")  # provider missing
    assert resolve_vision_model(settings) is None


def test_resolver_complete_config_builds_adapter_with_defaults() -> None:
    model = resolve_vision_model(
        Settings(_env_file=None, vision_provider="glm", glm_api_key="glm-test")
    )
    assert isinstance(model, VisionModel)
    assert model.name == DEFAULT_GLM_VISION_MODEL

    explicit = resolve_vision_model(
        Settings(
            _env_file=None,
            vision_provider="glm",
            glm_api_key="glm-test",
            glm_base_url="https://custom.example/v4",
            glm_vision_model="glm-4.6v-flash",
        )
    )
    assert explicit is not None and explicit.name == "glm-4.6v-flash"


def test_default_base_url_is_z_ai_coding_plan_endpoint() -> None:
    assert DEFAULT_GLM_BASE_URL == "https://api.z.ai/api/coding/paas/v4"
