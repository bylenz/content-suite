"""Creative AI endpoints (spec 04, fase 2): generate/regenerate/consistency-check.

All model calls go through the deterministic `app.ai.fakes` adapters: zero
network. Knowledge seeding reuses the real sync machine (`seed_synced_knowledge`),
so chunks, evidence and the vector space always match `FakeEmbeddingModel`.
"""

import asyncio
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.fakes import FakeEmbeddingModel, FakeTextModel
from app.brand_dna.models import BrandDnaStatus, BrandDnaVersion
from app.creative.models import CreativeItem, CreativeVersion, WorkflowEvent
from app.creative.router import (
    get_embedding_adapter,
    get_text_adapter,
    get_tracer_adapter,
)
from app.identity.models import BrandRole
from app.knowledge import service as knowledge_service
from app.observability.noop import NoopTracer
from app.observability.ports import CapabilitySpan
from tests.conftest import auth_header, make_workspace, seed_synced_knowledge
from tests.test_creative_items import create_item
from tests.test_creative_versions import output_for, post_version

NOOP = NoopTracer()

TASK_BY_TYPE = {
    "PRODUCT_DESCRIPTION": "TEXT",
    "VIDEO_SCRIPT": "TEXT",
    "IMAGE_PROMPT": "VISUAL",
}

CONSISTENCY_PAYLOAD = {
    "checks": [{"check_id": "check-tone", "label": "Tone of voice", "status": "fail"}],
    "findings": [
        {
            "rule_id": "tone-warm",
            "category": "tone",
            "expected": "Warm tone",
            "detected": "Cold register",
            "evidence": "Opening sentence reads distant.",
            "recommendation": "Rewrite the opening like a friend sharing a recipe.",
            "severity": "medium",
            "status": "fail",
        }
    ],
    "summary": "Un hallazgo de tono medio.",
}


class FakeTracer:
    """Records spans and returns a stable trace id (mirrors the port contract)."""

    def __init__(self, trace_id: str = "trace-test-1") -> None:
        self.spans: list[CapabilitySpan] = []
        self._trace_id = trace_id

    async def emit_span(self, span: CapabilitySpan) -> str | None:
        self.spans.append(span)
        return self._trace_id


def install_adapters(text: Any, tracer: FakeTracer | None = None) -> FakeTracer:
    """Override the creative router composition roots with test doubles."""
    from app.main import app

    tracer = tracer or FakeTracer()
    app.dependency_overrides[get_text_adapter] = lambda: text
    app.dependency_overrides[get_embedding_adapter] = lambda: FakeEmbeddingModel()
    app.dependency_overrides[get_tracer_adapter] = lambda: tracer
    return tracer


def synced_workspace(session: Session) -> dict[str, Any]:
    workspace = make_workspace(session, roles=(BrandRole.CREATOR, BrandRole.CONTENT_REVIEWER))
    seed_synced_knowledge(
        session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id
    )
    return workspace


def task_mandatory_ids(session: Session, brand_id: uuid.UUID, task: str) -> list[str]:
    """Mandatory rule ids for a task scope, straight from the context builder."""
    context = asyncio.run(
        knowledge_service.build_context(
            session,
            brand_id=brand_id,
            task=task,
            query="test query",
            embedding_adapter=FakeEmbeddingModel(),
            tracer=NOOP,
        )
    )
    return [str(rule.id) for rule in context.mandatory]


def active_dna_version_id(session: Session, brand_id: uuid.UUID) -> uuid.UUID:
    return session.execute(
        select(BrandDnaVersion.id).where(
            BrandDnaVersion.brand_id == brand_id,
            BrandDnaVersion.status == BrandDnaStatus.ACTIVE,
        )
    ).scalars().one()


def generate(client: TestClient, token: str, item_id, endpoint: str = "generate"):
    return client.post(f"/api/v1/creative-items/{item_id}/{endpoint}", headers=auth_header(token))


def consistency_check(client: TestClient, token: str, item_id):
    return client.post(
        f"/api/v1/creative-items/{item_id}/consistency-check", headers=auth_header(token)
    )


def version_rows(session: Session, item_id) -> list[CreativeVersion]:
    return list(
        session.scalars(
            select(CreativeVersion)
            .where(CreativeVersion.creative_item_id == uuid.UUID(str(item_id)))
            .order_by(CreativeVersion.version)
        )
    )


def test_generate_creates_ai_version_for_each_type(client: TestClient, session: Session):
    for item_type, task in TASK_BY_TYPE.items():
        workspace = synced_workspace(session)
        token = workspace["tokens"][BrandRole.CREATOR]
        item = create_item(
            client,
            token,
            workspace["brand_id"],
            item_type=item_type,
            brief={"audience": "Gen Z in Peru", "angle": "launch"},
        ).json()
        install_adapters(FakeTextModel(structured_output=output_for(item_type.lower())))

        response = generate(client, token, item["id"])

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["version"] == 2
        assert body["origin"] == "AI_GENERATED"
        assert body["brief"] == {"audience": "Gen Z in Peru", "angle": "launch"}
        assert body["output"]["content_type"] == item_type.lower()
        assert body["langfuse_trace_id"] == "trace-test-1"
        # Pinned to the exact Brand DNA version whose knowledge built the context.
        active_id = active_dna_version_id(session, workspace["brand_id"])
        assert body["brand_dna_version_id"] == str(active_id)
        # Applied rules are the real mandatory set of the task scope.
        assert body["applied_rule_ids"] == task_mandatory_ids(
            session, workspace["brand_id"], task
        )


def test_generate_persists_model_cited_rule_when_it_is_real(client, session):
    workspace = synced_workspace(session)
    token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, token, workspace["brand_id"]).json()
    real_id = task_mandatory_ids(session, workspace["brand_id"], "TEXT")[0]
    payload = output_for("product_description")
    payload["applied_rule_ids"] = [real_id]
    install_adapters(FakeTextModel(structured_output=payload))

    response = generate(client, token, item["id"])

    assert response.status_code == 201
    assert response.json()["applied_rule_ids"] == [real_id]


def test_generate_drops_fabricated_rule_ids(client, session):
    workspace = synced_workspace(session)
    token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, token, workspace["brand_id"]).json()
    payload = output_for("product_description")
    payload["applied_rule_ids"] = ["rule-made-up-by-model"]
    install_adapters(FakeTextModel(structured_output=payload))

    response = generate(client, token, item["id"])

    assert response.status_code == 201
    # Fabricated refs never persist; the mandatory floor is the honest answer.
    assert response.json()["applied_rule_ids"] == task_mandatory_ids(
        session, workspace["brand_id"], "TEXT"
    )


def test_generate_request_carries_retrieved_context(client, session):
    workspace = synced_workspace(session)
    token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, token, workspace["brand_id"]).json()
    text = FakeTextModel(structured_output=output_for("product_description"))
    install_adapters(text)

    assert generate(client, token, item["id"]).status_code == 201

    (call,) = text.calls
    assert call["op"] == "generate_structured"
    assert "BRAND CONTEXT (Brand DNA version" in call["prompt"]
    assert "MANDATORY RULES (always apply):" in call["prompt"]
    assert "rule_id=" in call["prompt"]
    assert item["title"] in call["prompt"]


def test_regenerates_as_new_version_with_regenerated_origin(client, session):
    workspace = synced_workspace(session)
    token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, token, workspace["brand_id"]).json()
    install_adapters(FakeTextModel(structured_output=output_for("product_description")))

    first = generate(client, token, item["id"])
    second = generate(client, token, item["id"], endpoint="regenerate")

    assert first.json()["origin"] == "AI_GENERATED"
    assert second.status_code == 201
    assert second.json()["version"] == 3
    assert second.json()["origin"] == "AI_REGENERATED"
    # Every version stays immutable: v1 (brief) and v2 (first AI output) intact.
    rows = {row.version: row for row in version_rows(session, item["id"])}
    assert rows[1].output is None and rows[2].output is not None and rows[3].output is not None


def test_generate_traces_span_bound_to_created_version(client, session):
    workspace = synced_workspace(session)
    token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, token, workspace["brand_id"]).json()
    tracer = install_adapters(FakeTextModel(structured_output=output_for("product_description")))

    response = generate(client, token, item["id"])

    version_id = response.json()["id"]
    spans = [s for s in tracer.spans if s.prompt_version == "creative.product_description.v1"]
    assert len(spans) == 1
    span = spans[0]
    assert span.entity == f"creative_item:{item['id']}"
    assert span.entity_type == "creative_version" and span.entity_id == version_id
    assert span.brand_id == str(workspace["brand_id"])
    assert span.summary is not None and span.summary.content_type == "product_description"
    assert span.model == "fake-text-model" and span.latency_ms >= 0
    # Retrieval is traced too (knowledge context builder span).
    assert any(s.operation == "knowledge.retrieve" for s in tracer.spans)


def test_consistency_check_persists_score_without_touching_content(client, session):
    workspace = synced_workspace(session)
    token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, token, workspace["brand_id"]).json()
    install_adapters(FakeTextModel(structured_output=output_for("product_description")))
    assert generate(client, token, item["id"]).status_code == 201
    before = version_rows(session, item["id"])[-1]
    install_adapters(FakeTextModel(structured_output=CONSISTENCY_PAYLOAD))

    response = consistency_check(client, token, item["id"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version"] == 2  # no new version: audit only
    assert body["consistency_score"] == 90.0  # 100 - medium(10)
    assert body["consistency_result"]["summary"] == "Un hallazgo de tono medio."
    assert body["consistency_result"]["trace_id"] == "trace-test-1"
    after = version_rows(session, item["id"])[-1]
    assert after.id == before.id
    assert after.output == before.output  # content columns never mutated
    assert after.brief == before.brief
    assert after.applied_rule_ids == before.applied_rule_ids
    assert after.langfuse_trace_id == "trace-test-1"  # generation trace preserved


def test_consistency_check_without_content_is_422(client, session):
    workspace = synced_workspace(session)
    token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, token, workspace["brand_id"]).json()
    install_adapters(FakeTextModel(structured_output=CONSISTENCY_PAYLOAD))

    response = consistency_check(client, token, item["id"])

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_consistency_check_fails_safe_without_knowledge(client, session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, token, workspace["brand_id"]).json()
    post_version(client, token, item["id"], output_for("product_description"))
    text = FakeTextModel(structured_output=CONSISTENCY_PAYLOAD)
    install_adapters(text)

    response = consistency_check(client, token, item["id"])

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "KNOWLEDGE_NOT_AVAILABLE"
    assert not text.calls  # provider never invoked
    row = version_rows(session, item["id"])[-1]
    assert row.consistency_result is None and row.consistency_score is None


@pytest.mark.parametrize("status_value", ["NOT_SYNCED", "OUTDATED"])
def test_generate_fails_safe_without_synced_knowledge(client, session, status_value):
    from app.brand_dna.models import KnowledgeStatus

    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    dna = seed_synced_knowledge(
        session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id
    )
    fresh = session.get(BrandDnaVersion, dna.id)
    assert fresh is not None
    fresh.knowledge_status = KnowledgeStatus(status_value)
    session.commit()
    item = create_item(client, token, workspace["brand_id"]).json()
    text = FakeTextModel(structured_output=output_for("product_description"))
    install_adapters(text)

    response = generate(client, token, item["id"])

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "KNOWLEDGE_NOT_AVAILABLE"
    assert not text.calls  # provider never invoked (fail-safe ordering)
    assert len(version_rows(session, item["id"])) == 1  # nothing persisted


def test_generate_503_without_active_brand_dna(client, session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, token, workspace["brand_id"]).json()
    install_adapters(FakeTextModel(structured_output=output_for("product_description")))

    response = generate(client, token, item["id"])

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "KNOWLEDGE_NOT_AVAILABLE"


def test_generate_503_when_text_provider_unconfigured(client, session):
    workspace = synced_workspace(session)
    token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, token, workspace["brand_id"]).json()
    install_adapters(None)

    response = generate(client, token, item["id"])

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"


def test_generate_with_invalid_structured_output_persists_nothing(client, session):
    workspace = synced_workspace(session)
    token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, token, workspace["brand_id"]).json()
    install_adapters(FakeTextModel(structured_output={"content_type": "bogus", "title": "x"}))

    response = generate(client, token, item["id"])

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "AI_OUTPUT_INVALID"
    assert error["details"]["contract"] == "CreativeOutput"
    assert len(version_rows(session, item["id"])) == 1  # no partial version


def test_reviewer_cannot_generate(client, session):
    workspace = synced_workspace(session)
    reviewer_token = workspace["tokens"][BrandRole.CONTENT_REVIEWER]
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, creator_token, workspace["brand_id"]).json()
    install_adapters(FakeTextModel(structured_output=output_for("product_description")))

    response = generate(client, reviewer_token, item["id"])

    assert response.status_code == 403


def test_generate_by_non_member_is_404(client, session):
    workspace = synced_workspace(session)
    other = make_workspace(session, roles=(BrandRole.CREATOR,))
    item = create_item(client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"]).json()
    install_adapters(FakeTextModel(structured_output=output_for("product_description")))

    response = generate(client, other["tokens"][BrandRole.CREATOR], item["id"])

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_generate_while_pending_review_is_409(client, session):
    workspace = synced_workspace(session)
    token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, token, workspace["brand_id"]).json()
    install_adapters(FakeTextModel(structured_output=output_for("product_description")))
    generated = generate(client, token, item["id"]).json()
    submitted = client.post(
        f"/api/v1/creative-items/{item['id']}/submit",
        headers=auth_header(token),
        json={"version_id": generated["id"]},
    )
    assert submitted.status_code == 200

    response = generate(client, token, item["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_WORKFLOW_TRANSITION"


def test_submit_fails_safe_without_synced_knowledge(client, session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, token, workspace["brand_id"]).json()
    version = post_version(client, token, item["id"], output_for("product_description")).json()

    response = client.post(
        f"/api/v1/creative-items/{item['id']}/submit",
        headers=auth_header(token),
        json={"version_id": version["id"]},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "KNOWLEDGE_NOT_AVAILABLE"
    # No transition and no event when the guard rejects.
    fresh = session.get(CreativeItem, uuid.UUID(item["id"]))
    assert fresh is not None and fresh.workflow_status.value == "DRAFT"
    assert not session.scalars(
        select(WorkflowEvent).where(WorkflowEvent.creative_item_id == uuid.UUID(item["id"]))
    ).all()


def test_applied_context_reflects_the_generation(client, session):
    workspace = synced_workspace(session)
    token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, token, workspace["brand_id"]).json()
    install_adapters(FakeTextModel(structured_output=output_for("product_description")))
    generated = generate(client, token, item["id"]).json()

    response = client.get(
        f"/api/v1/creative-items/{item['id']}/applied-context", headers=auth_header(token)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["version_id"] == generated["id"]
    assert body["brand_dna_version_id"] == generated["brand_dna_version_id"]
    assert body["applied_rule_ids"] == generated["applied_rule_ids"]
    assert body["applied_rule_ids"] == task_mandatory_ids(session, workspace["brand_id"], "TEXT")
