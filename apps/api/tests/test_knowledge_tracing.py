"""Knowledge tracing extension (5.1): TraceSummary Knowledge contracts/rules,
Langfuse observation naming (prompt spans of 005 + the three Knowledge
operations), CapabilitySpan name invariant. Stubbed SDK, no network."""

import asyncio

import pytest
from pydantic import ValidationError

from app.ai.contracts import TraceSummary
from app.observability.langfuse_adapter import LangfuseTracer
from app.observability.ports import CapabilitySpan


class StubObservation:
    def __init__(self) -> None:
        self.updates: list[dict] = []
        self.ended = False

    def update(self, **kwargs) -> None:
        self.updates.append(kwargs)

    def end(self) -> None:
        self.ended = True


class StubLangfuseClient:
    def __init__(self) -> None:
        self.started: list[dict] = []
        self.last_observation: StubObservation | None = None

    def start_observation(self, **kwargs) -> StubObservation:
        self.started.append(kwargs)
        self.last_observation = StubObservation()
        return self.last_observation


def test_knowledge_summary_values_are_accepted() -> None:
    sync = TraceSummary(contract="KnowledgeSync", ok=True, chunk_count=12)
    embed = TraceSummary(contract="KnowledgeEmbed", ok=False, chunk_count=12)
    retrieve = TraceSummary(
        contract="KnowledgeRetrieval", ok=True, mandatory_count=5, semantic_count=8
    )
    assert sync.model_dump() == {
        "contract": "KnowledgeSync", "ok": True, "chunk_count": 12,
        "check_count": 0, "finding_count": 0,
    }
    assert embed.model_dump() == {
        "contract": "KnowledgeEmbed", "ok": False, "chunk_count": 12,
        "check_count": 0, "finding_count": 0,
    }
    assert retrieve.model_dump() == {
        "contract": "KnowledgeRetrieval", "ok": True,
        "mandatory_count": 5, "semantic_count": 8,
        "check_count": 0, "finding_count": 0,
    }


def test_knowledge_counts_are_rejected_on_non_knowledge_contracts() -> None:
    with pytest.raises(ValidationError):
        TraceSummary(contract="CreativeOutput", ok=True, content_type="product_description",
                     chunk_count=3)
    with pytest.raises(ValidationError):
        TraceSummary(contract="ConsistencyResult", ok=True, check_count=1, semantic_count=2)


def test_knowledge_contracts_reject_nonzero_check_or_finding_counts() -> None:
    with pytest.raises(ValidationError):
        TraceSummary(contract="KnowledgeSync", ok=True, check_count=1)
    with pytest.raises(ValidationError):
        TraceSummary(contract="KnowledgeRetrieval", ok=True, finding_count=2)


def test_knowledge_counts_are_bounded() -> None:
    with pytest.raises(ValidationError):
        TraceSummary(contract="KnowledgeSync", ok=True, chunk_count=10001)


def test_existing_contracts_keep_default_zero_counts() -> None:
    summary = TraceSummary(contract="ConsistencyResult", ok=True)
    assert summary.check_count == 0
    assert summary.finding_count == 0
    assert summary.chunk_count is None


def test_prompt_span_keeps_its_exact_observation_name_and_metadata() -> None:
    client = StubLangfuseClient()
    span = CapabilitySpan(
        entity="creative_item:1", prompt_version="consistency.text.v1",
        model="fake-text", latency_ms=1.0,
    )
    asyncio.run(LangfuseTracer(client).emit_span(span))
    assert client.started[0]["name"] == "consistency.text.v1"
    assert client.last_observation is not None
    metadata = client.last_observation.updates[0]["metadata"]
    assert set(metadata) == {
        "entity", "prompt_version", "model", "latency_ms", "summary", "error",
    }


def test_knowledge_operations_name_the_observation_and_add_operation_metadata() -> None:
    client = StubLangfuseClient()
    tracer = LangfuseTracer(client)
    for operation in ("knowledge.sync", "knowledge.embed", "knowledge.retrieve"):
        span = CapabilitySpan(
            entity="brand_knowledge:abc", model="fake-embedding", latency_ms=2.0,
            operation=operation,
        )
        asyncio.run(tracer.emit_span(span))
    names = [call["name"] for call in client.started]
    assert names == ["knowledge.sync", "knowledge.embed", "knowledge.retrieve"]
    assert client.last_observation is not None
    for update in client.last_observation.updates:
        assert update["metadata"]["operation"] in names
        assert update["metadata"]["prompt_version"] is None


def test_anonymous_span_is_rejected_at_construction() -> None:
    with pytest.raises(ValueError):
        CapabilitySpan(entity="brand_knowledge:abc", model=None, latency_ms=1.0)
