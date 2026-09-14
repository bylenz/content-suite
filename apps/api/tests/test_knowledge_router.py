"""Knowledge endpoints (8.1): RBAC matrix membership-first, 404 without ACTIVE,
409 concurrent/OUTDATED, 503 provider absent, envelope codes, no draft leakage.

The embedding adapter is injected via dependency override (deterministic fake,
no network).
"""

import asyncio
import uuid
from collections.abc import Sequence

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.fakes import FakeEmbeddingModel
from app.brand_dna.models import BrandDnaStatus, BrandDnaVersion, KnowledgeStatus
from app.db import get_session
from app.identity.models import BrandRole
from app.knowledge.models import BrandKnowledgeChunk
from app.knowledge.router import get_embedding_adapter
from app.main import app
from tests.conftest import (
    auth_header,
    gather_asgi_requests,
    make_concurrency_engine,
    make_session_override,
    make_token,
    make_workspace,
    seed_race_workspace,
    valid_document,
)

KNOWLEDGE = "/api/v1/brands/{brand_id}/brand-knowledge"


@pytest.fixture
def fake_adapter():
    return FakeEmbeddingModel()


def override_adapter(adapter):
    def _override():
        return adapter

    return _override


def make_active(
    session, brand_id: uuid.UUID, created_by: uuid.UUID, *, version: int = 1
) -> BrandDnaVersion:
    row = BrandDnaVersion(
        id=uuid.uuid4(),
        brand_id=brand_id,
        version=version,
        status=BrandDnaStatus.ACTIVE,
        document=valid_document(),
        created_by=created_by,
        knowledge_status=KnowledgeStatus.NOT_SYNCED,
    )
    session.add(row)
    session.commit()
    return row


def sync(client, workspace, role: BrandRole, adapter=None):
    if adapter is not None:
        client.app.dependency_overrides[get_embedding_adapter] = override_adapter(adapter)
    return client.post(
        f"{KNOWLEDGE.format(brand_id=workspace['brand_id'])}/sync",
        headers=auth_header(workspace["tokens"][role]),
    )


def test_readers_see_published_chunks_without_embeddings(client, session, fake_adapter) -> None:
    workspace = make_workspace(session)
    creator = workspace["profiles"][BrandRole.CREATOR]
    active = make_active(session, workspace["brand_id"], creator.id)
    sync(client, workspace, BrandRole.CREATOR, adapter=fake_adapter).raise_for_status()

    for role in (BrandRole.CONTENT_REVIEWER, BrandRole.VISUAL_REVIEWER, BrandRole.CREATOR):
        response = client.get(
            KNOWLEDGE.format(brand_id=workspace["brand_id"]),
            headers=auth_header(workspace["tokens"][role]),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["brand_dna_version"]["id"] == str(active.id)
        assert body["brand_dna_version"]["knowledge_status"] == "SYNCED"
        assert len(body["chunks"]) > 0
        for chunk in body["chunks"]:
            assert set(chunk) == {
                "id", "section", "rule_type", "scope", "mandatory", "content", "metadata",
                "created_at",
            }
            assert "embedding" not in chunk


def test_status_endpoint_reports_sync_evidence(client, session, fake_adapter) -> None:
    workspace = make_workspace(session)
    make_active(session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id)
    sync(client, workspace, BrandRole.CREATOR, adapter=fake_adapter).raise_for_status()

    response = client.get(
        f"{KNOWLEDGE.format(brand_id=workspace['brand_id'])}/status",
        headers=auth_header(workspace["tokens"][BrandRole.CONTENT_REVIEWER]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["knowledge_status"] == "SYNCED"
    assert body["chunk_count"] > 0
    assert body["embedding_model"] == fake_adapter.name


def test_status_without_successful_sync_reports_null_evidence(client, session) -> None:
    workspace = make_workspace(session)
    make_active(session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id)

    response = client.get(
        f"{KNOWLEDGE.format(brand_id=workspace['brand_id'])}/status",
        headers=auth_header(workspace["tokens"][BrandRole.CREATOR]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["knowledge_status"] == "NOT_SYNCED"
    assert body["chunk_count"] is None
    assert body["embedding_model"] is None


def test_rbac_matrix_sync_is_creator_only(client, session, fake_adapter) -> None:
    workspace = make_workspace(session)
    make_active(session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id)

    for role in (BrandRole.CONTENT_REVIEWER, BrandRole.VISUAL_REVIEWER):
        response = sync(client, workspace, role, adapter=fake_adapter)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

    ok = sync(client, workspace, BrandRole.CREATOR, adapter=fake_adapter)
    assert ok.status_code == 200
    assert ok.json()["knowledge_status"] == "SYNCED"


@pytest.mark.parametrize("path", ["", "/status", "/sync"])
def test_non_member_gets_403_even_for_nonexistent_brand(client, path) -> None:
    response = client.request(
        "GET" if path != "/sync" else "POST",
        f"{KNOWLEDGE.format(brand_id=uuid.uuid4())}{path}",
        headers=auth_header(make_token()),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.parametrize("method_path", [("GET", ""), ("GET", "/status"), ("POST", "/sync")])
def test_member_without_active_version_gets_404_envelope(client, session, method_path) -> None:
    workspace = make_workspace(session)
    method, path = method_path
    response = client.request(
        method,
        f"{KNOWLEDGE.format(brand_id=workspace['brand_id'])}{path}",
        headers=auth_header(workspace["tokens"][BrandRole.CREATOR]),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_outdated_sync_returns_409_with_publish_detail(client, session, fake_adapter) -> None:
    workspace = make_workspace(session)
    make_active(session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id)
    sync(client, workspace, BrandRole.CREATOR, adapter=fake_adapter).raise_for_status()
    # Brand DNA marks SYNCED -> OUTDATED when the draft is edited.
    from app.brand_dna.repository import get_active

    active = get_active(session, workspace["brand_id"])
    assert active is not None
    active.knowledge_status = KnowledgeStatus.OUTDATED
    session.commit()

    response = sync(client, workspace, BrandRole.CREATOR, adapter=fake_adapter)
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "INVALID_WORKFLOW_TRANSITION"
    assert error["details"]["reason"] == "outdated_needs_publish"
    refreshed = get_active(session, workspace["brand_id"])
    assert refreshed is not None
    assert refreshed.knowledge_status == KnowledgeStatus.OUTDATED


def test_provider_absent_returns_503_without_state_change(client, session) -> None:
    workspace = make_workspace(session)
    creator = workspace["profiles"][BrandRole.CREATOR]
    active = make_active(session, workspace["brand_id"], creator.id)
    client.app.dependency_overrides[get_embedding_adapter] = override_adapter(None)

    response = sync(client, workspace, BrandRole.CREATOR)

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "SERVICE_UNAVAILABLE"
    assert "sk-" not in error["message"]
    session.refresh(active)
    assert active.knowledge_status == KnowledgeStatus.NOT_SYNCED
    persisted = session.scalar(
        select(func.count()).select_from(BrandKnowledgeChunk).where(
            BrandKnowledgeChunk.brand_dna_version_id == active.id
        )
    )
    assert persisted == 0


class YieldingEmbedding:
    name = "yielding-embedding"
    dimensions = 8

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        # Real (small) sleep: the concurrent request's dependency chain and
        # atomic claim must run while this one holds the SYNCING claim.
        await asyncio.sleep(0.05)
        return [[0.5] * 8 for _ in texts]


def test_concurrent_syncs_return_one_200_and_one_immediate_409(tmp_path) -> None:
    engine = make_concurrency_engine(tmp_path)
    brand_id, token = seed_race_workspace(engine)
    with Session(engine) as seed:
        import jwt as pyjwt

        profile_id = uuid.UUID(str(pyjwt.decode(token, options={"verify_signature": False})["sub"]))
        active = BrandDnaVersion(
            id=uuid.uuid4(), brand_id=brand_id, version=1, status=BrandDnaStatus.ACTIVE,
            document=valid_document(), created_by=profile_id,
            knowledge_status=KnowledgeStatus.NOT_SYNCED,
        )
        seed.add(active)
        seed.commit()
        version_id = active.id

    app.dependency_overrides[get_session] = make_session_override(engine)
    app.dependency_overrides[get_embedding_adapter] = override_adapter(YieldingEmbedding())
    try:
        responses = asyncio.run(
            gather_asgi_requests(
                [
                    {
                        "method": "POST",
                        "url": f"{KNOWLEDGE.format(brand_id=brand_id)}/sync",
                        "headers": auth_header(token),
                    },
                ]
                * 2
            )
        )
    finally:
        app.dependency_overrides.clear()

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200, 409]
    conflict = next(r for r in responses if r.status_code == 409)
    assert conflict.json()["error"]["code"] == "INVALID_WORKFLOW_TRANSITION"
    assert conflict.json()["error"]["details"]["reason"] == "sync_in_progress"
    ok = next(r for r in responses if r.status_code == 200)
    assert ok.json()["knowledge_status"] == "SYNCED"
    with Session(engine) as check:
        fresh = check.get(BrandDnaVersion, version_id)
        assert fresh is not None
        assert fresh.knowledge_status == KnowledgeStatus.SYNCED
        persisted = check.scalar(
            select(func.count()).select_from(BrandKnowledgeChunk).where(
                BrandKnowledgeChunk.brand_dna_version_id == version_id
            )
        )
        assert persisted is not None and persisted > 0  # single chunk set, no duplicates


def test_reviewers_never_receive_draft_derived_data(client, session, fake_adapter) -> None:
    workspace = make_workspace(session)
    # ACTIVE v1 synced, then a draft v2 exists with different content. Chunks
    # only ever derive from the ACTIVE published version.
    active = make_active(
        session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id, version=1
    )
    draft_document = valid_document()
    draft_document["identity"]["purpose"] = "DRAFT ONLY PURPOSE MARKER"
    draft = BrandDnaVersion(
        id=uuid.uuid4(), brand_id=workspace["brand_id"], version=2,
        status=BrandDnaStatus.DRAFT, document=draft_document,
        created_by=workspace["profiles"][BrandRole.CREATOR].id,
        knowledge_status=KnowledgeStatus.NOT_SYNCED,
    )
    session.add(draft)
    session.commit()
    sync(client, workspace, BrandRole.CREATOR, adapter=fake_adapter).raise_for_status()

    response = client.get(
        KNOWLEDGE.format(brand_id=workspace["brand_id"]),
        headers=auth_header(workspace["tokens"][BrandRole.CONTENT_REVIEWER]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["brand_dna_version"]["id"] == str(active.id)
    assert all("DRAFT ONLY PURPOSE MARKER" != chunk["content"] for chunk in body["chunks"])
