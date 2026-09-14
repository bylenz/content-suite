"""OpenAI embeddings adapter + resolver (3.2): stubbed SDK, no network.

Covers: batching/order via `index`, declared `name`/`dimensions` without any
provider call, SDK errors -> explicit exception, resolution absent/partial/
complete (including unknown model without explicit dimensions -> None,
reduced dimensions for text-embedding-3-* and the fixed dimension of
ada-002), SDK import isolation.
"""

import asyncio
import logging
from collections.abc import Iterator
from typing import Any

import pytest

from app.ai.fakes import FakeEmbeddingModel
from app.ai.ports import EmbeddingModel
from app.ai.providers import resolve_embedding_model
from app.ai.providers.openai_embeddings import OpenAIEmbeddingModel
from app.config import Settings


class StubEmbeddings:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self.fail = fail

    def create(self, **params: Any) -> Any:
        self.calls.append(params)
        if self.fail:
            raise RuntimeError("sdk exploded with secret sk-test")

        class Item:
            def __init__(self, index: int) -> None:
                self.index = index
                self.embedding = [float(index), 1.0]

        class Response:
            # Deliberately shuffled: `index` must restore the input order.
            data = [Item(1), Item(0)]

        return Response()


class StubOpenAIClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.embeddings = StubEmbeddings(fail=fail)


@pytest.fixture(autouse=True)
def _fresh_resolution_cache() -> Iterator[None]:
    from app.ai import providers

    providers._resolve_cached.cache_clear()
    yield
    providers._resolve_cached.cache_clear()


def test_embed_batches_and_restores_order_via_index() -> None:
    client = StubOpenAIClient()
    model = OpenAIEmbeddingModel(
        api_key="sk-test", model="text-embedding-3-small", dimensions=2, client=client
    )

    vectors = asyncio.run(model.embed(["a", "b"]))

    assert client.embeddings.calls == [
        {"input": ["a", "b"], "model": "text-embedding-3-small", "dimensions": 2}
    ]
    assert vectors == [[0.0, 1.0], [1.0, 1.0]]  # ordered by `index`, not list order


def test_fixed_dimension_model_omits_the_dimensions_param() -> None:
    client = StubOpenAIClient()
    model = OpenAIEmbeddingModel(
        api_key="sk-test", model="text-embedding-ada-002", dimensions=1536, client=client
    )

    asyncio.run(model.embed(["a"]))

    assert client.embeddings.calls == [{"input": ["a"], "model": "text-embedding-ada-002"}]


def test_name_and_dimensions_are_declared_without_provider_calls() -> None:
    client = StubOpenAIClient()
    model = OpenAIEmbeddingModel(
        api_key="sk-test", model="text-embedding-3-large", dimensions=512, client=client
    )

    assert model.name == "text-embedding-3-large"
    assert model.dimensions == 512
    assert client.embeddings.calls == []  # no provider call to know name/dimensions
    assert isinstance(model, EmbeddingModel)


def test_sdk_error_propagates_as_explicit_exception() -> None:
    model = OpenAIEmbeddingModel(
        api_key="sk-test", model="text-embedding-3-small", dimensions=2,
        client=StubOpenAIClient(fail=True),
    )

    with pytest.raises(RuntimeError):
        asyncio.run(model.embed(["a"]))


def test_absent_config_resolves_none_with_single_info_log(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="app.ai.providers"):
        adapter = resolve_embedding_model(Settings(_env_file=None))
    assert adapter is None
    records = [r for r in caplog.records if "Embedding" in r.message]
    assert len(records) == 1
    assert records[0].levelno == logging.INFO


def test_partial_config_resolves_none_naming_missing_settings_without_values(caplog) -> None:
    settings = Settings(_env_file=None, ai_provider="openai")
    with caplog.at_level(logging.WARNING, logger="app.ai.providers"):
        adapter = resolve_embedding_model(settings)
    assert adapter is None
    records = [r for r in caplog.records if "Embedding" in r.message]
    assert len(records) == 1
    message = records[0].getMessage()
    assert records[0].levelno == logging.WARNING
    assert "CONTENT_SUITE_OPENAI_API_KEY" in message
    assert "sk-secret-value" not in message


def test_unsupported_provider_resolves_none_naming_the_required_setting(caplog) -> None:
    settings = Settings(_env_file=None, ai_provider="anthropic", openai_api_key="sk-test")
    with caplog.at_level(logging.WARNING, logger="app.ai.providers"):
        adapter = resolve_embedding_model(settings)
    assert adapter is None
    assert "CONTENT_SUITE_AI_PROVIDER=openai" in caplog.records[-1].getMessage()


def test_unknown_model_without_explicit_dimensions_resolves_none(caplog) -> None:
    settings = Settings(
        _env_file=None,
        ai_provider="openai",
        openai_api_key="sk-test",
        openai_embedding_model="text-embedding-future-9",
    )
    with caplog.at_level(logging.WARNING, logger="app.ai.providers"):
        adapter = resolve_embedding_model(settings)
    assert adapter is None
    assert "CONTENT_SUITE_OPENAI_EMBEDDING_DIMENSIONS" in caplog.records[-1].getMessage()


def test_fixed_dimension_model_with_mismatching_explicit_dimensions_resolves_none() -> None:
    settings = Settings(
        _env_file=None,
        ai_provider="openai",
        openai_api_key="sk-test",
        openai_embedding_model="text-embedding-ada-002",
        openai_embedding_dimensions=512,
    )
    assert resolve_embedding_model(settings) is None


def test_fixed_dimension_model_with_documented_dimension_resolves_the_adapter(monkeypatch) -> None:
    built: dict[str, Any] = {}

    def stub_init(self: OpenAIEmbeddingModel, *, api_key: str, model: str, dimensions: int,
                  client: Any = None) -> None:
        built.update(model=model, dimensions=dimensions)
        self.name, self.dimensions = model, dimensions

    monkeypatch.setattr(OpenAIEmbeddingModel, "__init__", stub_init)
    settings = Settings(
        _env_file=None,
        ai_provider="openai",
        openai_api_key="sk-test",
        openai_embedding_model="text-embedding-ada-002",
        openai_embedding_dimensions=1536,
    )
    adapter = resolve_embedding_model(settings)
    assert isinstance(adapter, OpenAIEmbeddingModel)
    assert adapter.dimensions == 1536


def test_reduced_dimensions_on_3_series_models_resolve_the_adapter(monkeypatch) -> None:
    built: dict[str, Any] = {}

    def stub_init(self: OpenAIEmbeddingModel, *, api_key: str, model: str, dimensions: int,
                  client: Any = None) -> None:
        built[f"{model}"] = dimensions
        self.name, self.dimensions = model, dimensions

    monkeypatch.setattr(OpenAIEmbeddingModel, "__init__", stub_init)
    small = resolve_embedding_model(
        Settings(
            _env_file=None,
            ai_provider="openai",
            openai_api_key="sk-test",
            openai_embedding_model="text-embedding-3-small",
            openai_embedding_dimensions=512,
        )
    )
    large = resolve_embedding_model(
        Settings(
            _env_file=None,
            ai_provider="openai",
            openai_api_key="sk-test",
            openai_embedding_model="text-embedding-3-large",
            openai_embedding_dimensions=256,
        )
    )
    assert isinstance(small, OpenAIEmbeddingModel)
    assert small.dimensions == 512  # reduced, provider `dimensions` parameter
    assert isinstance(large, OpenAIEmbeddingModel)
    assert large.dimensions == 256
    assert built == {"text-embedding-3-small": 512, "text-embedding-3-large": 256}


def test_complete_config_resolves_the_openai_adapter(monkeypatch) -> None:
    built: dict[str, Any] = {}

    def stub_init(self: OpenAIEmbeddingModel, *, api_key: str, model: str, dimensions: int,
                  client: Any = None) -> None:
        built.update(api_key=api_key, model=model, dimensions=dimensions)
        self.name, self.dimensions = model, dimensions

    monkeypatch.setattr(OpenAIEmbeddingModel, "__init__", stub_init)
    settings = Settings(
        _env_file=None,
        ai_provider="openai",
        openai_api_key="sk-test",
        openai_embedding_model="text-embedding-3-small",
    )
    adapter = resolve_embedding_model(settings)
    assert isinstance(adapter, OpenAIEmbeddingModel)
    assert adapter.name == "text-embedding-3-small"
    assert adapter.dimensions == 1536  # documented default, no provider call
    assert built["api_key"] == "sk-test"


def test_repeated_complete_resolution_builds_the_adapter_once(monkeypatch) -> None:
    built: list[int] = []

    def stub_init(self: OpenAIEmbeddingModel, *, api_key: str, model: str, dimensions: int,
                  client: Any = None) -> None:
        built.append(1)
        self.name, self.dimensions = model, dimensions

    monkeypatch.setattr(OpenAIEmbeddingModel, "__init__", stub_init)
    settings = Settings(_env_file=None, ai_provider="openai", openai_api_key="sk-test")
    first = resolve_embedding_model(settings)
    second = resolve_embedding_model(settings)
    assert first is second
    assert len(built) == 1


def test_fake_embedding_model_still_satisfies_the_extended_port() -> None:
    fake = FakeEmbeddingModel()
    assert isinstance(fake, EmbeddingModel)
    assert fake.dimensions == 8
