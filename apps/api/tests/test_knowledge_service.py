"""Knowledge service (6.1/6.2/7.1): sync machine, fail-safe context builder.

All embeddings come from deterministic fakes (005) or local stubs: no network.
SQLite is the documented test seam for ranking (Python cosine), not a pgvector
simulation.
"""

import asyncio
import uuid
import zlib
from collections.abc import Sequence
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.ai.errors import AIProviderNotConfiguredError
from app.ai.fakes import FakeEmbeddingModel
from app.brand_dna.models import BrandDnaStatus, BrandDnaVersion, KnowledgeStatus
from app.brand_dna.schemas import BrandDnaDocument
from app.identity.auth import AuthenticatedUser
from app.identity.models import BrandRole
from app.knowledge import repository, service
from app.knowledge.chunker import build_chunks
from app.knowledge.errors import KnowledgeNotAvailableError, SyncConflictError
from app.knowledge.models import KnowledgeScope
from app.observability.noop import NoopTracer
from app.observability.ports import CapabilitySpan
from tests.conftest import make_workspace, valid_document

NOOP = NoopTracer()


class RecordingTracer:
    def __init__(self) -> None:
        self.spans: list[CapabilitySpan] = []

    async def emit_span(self, span: CapabilitySpan) -> str | None:
        self.spans.append(span)
        return None


class FailingEmbedding:
    name = "failing-embedding"
    dimensions = 8

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise RuntimeError("provider exploded with secret")


class MalformedEmbedding:
    name = "malformed-embedding"
    dimensions = 8

    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.calls = 0

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += 1
        return self.vectors


class YieldingEmbedding:
    name = "yielding-embedding"
    dimensions = 4

    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += 1
        await asyncio.sleep(0)  # genuinely yield control to the concurrent task
        return [[0.5, 0.5, 0.5, 0.5] for _ in texts]


class OtherDimEmbedding(FakeEmbeddingModel):
    name = "other-dim-embedding"
    dimensions = 4

    @staticmethod
    def vector_for(text: str) -> list[float]:
        seed = (zlib.crc32(text.encode("utf-8")) % 1000) / 1000.0
        return [seed, 1.0 - seed, 0.5, 0.25]


def make_active_version(
    session: Session,
    brand_id: uuid.UUID,
    created_by: uuid.UUID,
    *,
    knowledge_status: KnowledgeStatus = KnowledgeStatus.NOT_SYNCED,
    version: int = 1,
) -> BrandDnaVersion:
    row = BrandDnaVersion(
        id=uuid.uuid4(),
        brand_id=brand_id,
        version=version,
        status=BrandDnaStatus.ACTIVE,
        document=valid_document(),
        created_by=created_by,
        knowledge_status=knowledge_status,
    )
    session.add(row)
    session.commit()
    return row


def make_user(workspace: dict[str, Any], role: BrandRole) -> AuthenticatedUser:
    profile = workspace["profiles"][role]
    return AuthenticatedUser(id=profile.id, email=profile.email)


def expected_chunk_count(version_id: uuid.UUID) -> int:
    chunks, _ = build_chunks(version_id, BrandDnaDocument.model_validate(valid_document()))
    return len(chunks)


def test_sync_transitions_not_synced_to_synced_and_persists_chunks(session) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    active = make_active_version(session, workspace["brand_id"], user.id)
    fake = FakeEmbeddingModel()
    tracer = RecordingTracer()

    result = asyncio.run(
        service.sync_knowledge(
            session, user=user, brand_id=workspace["brand_id"],
            embedding_adapter=fake, tracer=tracer,
        )
    )

    assert result.knowledge_status == KnowledgeStatus.SYNCED
    assert result.chunk_count == expected_chunk_count(active.id)
    assert result.embedding_model == fake.name
    fresh = session.get(BrandDnaVersion, active.id)
    assert fresh is not None
    assert fresh.knowledge_status == KnowledgeStatus.SYNCED
    assert fresh.knowledge_embedding_model == fake.name
    assert fresh.knowledge_embedding_dimensions == fake.dimensions
    assert fresh.knowledge_fingerprint is not None
    chunks = repository.list_chunks(
        session, brand_id=workspace["brand_id"], brand_dna_version_id=active.id
    )
    assert len(chunks) == result.chunk_count
    # Stable UUIDv5 identities: persisted ids equal the chunker's derivation.
    derived, _ = build_chunks(active.id, BrandDnaDocument.model_validate(valid_document()))
    assert {c.id for c in chunks} == {c.id for c in derived}
    assert all(c.embedding for c in chunks)


def test_synced_without_mismatch_is_idempotent_without_reembedding(session) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    active = make_active_version(session, workspace["brand_id"], user.id)
    fake = FakeEmbeddingModel()

    first = asyncio.run(
        service.sync_knowledge(
            session, user=user, brand_id=workspace["brand_id"],
            embedding_adapter=fake, tracer=NOOP,
        )
    )
    calls_after_first = len(fake.calls)
    second = asyncio.run(
        service.sync_knowledge(
            session, user=user, brand_id=workspace["brand_id"],
            embedding_adapter=fake, tracer=NOOP,
        )
    )

    assert second.knowledge_status == KnowledgeStatus.SYNCED
    assert second.chunk_count == first.chunk_count
    assert len(fake.calls) == calls_after_first  # no re-embedding
    assert (
        repository.count_chunks(session, active.id) == first.chunk_count
    )  # no duplication


def test_synced_with_model_mismatch_regenerates_embeddings(session) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    make_active_version(session, workspace["brand_id"], user.id)

    asyncio.run(
        service.sync_knowledge(
            session, user=user, brand_id=workspace["brand_id"],
            embedding_adapter=FakeEmbeddingModel(), tracer=NOOP,
        )
    )

    class RenamedFake(FakeEmbeddingModel):
        name = "renamed-embedding"

    second = asyncio.run(
        service.sync_knowledge(
            session, user=user, brand_id=workspace["brand_id"],
            embedding_adapter=RenamedFake(), tracer=NOOP,
        )
    )

    assert second.embedding_model == "renamed-embedding"


def test_synced_with_dimension_mismatch_regenerates_embeddings(session) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    active = make_active_version(session, workspace["brand_id"], user.id)

    asyncio.run(
        service.sync_knowledge(
            session, user=user, brand_id=workspace["brand_id"],
            embedding_adapter=FakeEmbeddingModel(), tracer=NOOP,
        )
    )
    # Corrupt the persisted dimension evidence: mismatch must trigger regeneration
    # even though the model name matches (vector space differs).
    active.knowledge_embedding_dimensions = FakeEmbeddingModel.dimensions + 1
    session.commit()

    result = asyncio.run(
        service.sync_knowledge(
            session, user=user, brand_id=workspace["brand_id"],
            embedding_adapter=OtherDimEmbedding(), tracer=NOOP,
        )
    )
    assert result.knowledge_status == KnowledgeStatus.SYNCED


def test_synced_with_fingerprint_mismatch_regenerates_embeddings(session) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    active = make_active_version(session, workspace["brand_id"], user.id)

    asyncio.run(
        service.sync_knowledge(
            session, user=user, brand_id=workspace["brand_id"],
            embedding_adapter=FakeEmbeddingModel(), tracer=NOOP,
        )
    )
    canonical = active.knowledge_fingerprint
    # Corrupt fingerprint: derived chunks no longer match the immutable document.
    active.knowledge_fingerprint = "0" * 64
    session.commit()
    fake = FakeEmbeddingModel()
    result = asyncio.run(
        service.sync_knowledge(
            session, user=user, brand_id=workspace["brand_id"],
            embedding_adapter=fake, tracer=NOOP,
        )
    )
    fresh = session.get(BrandDnaVersion, active.id)
    assert fresh is not None
    assert result.knowledge_status == KnowledgeStatus.SYNCED
    assert fresh.knowledge_fingerprint == canonical  # evidence restored
    assert fake.calls  # regeneration actually re-embedded


def test_missing_adapter_is_503_without_state_transition(session) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    active = make_active_version(session, workspace["brand_id"], user.id)

    with pytest.raises(AIProviderNotConfiguredError):
        asyncio.run(
            service.sync_knowledge(
                session, user=user, brand_id=workspace["brand_id"],
                embedding_adapter=None, tracer=NOOP,
            )
        )

    fresh = session.get(BrandDnaVersion, active.id)
    assert fresh is not None
    assert fresh.knowledge_status == KnowledgeStatus.NOT_SYNCED  # untouched
    assert repository.count_chunks(session, active.id) == 0


@pytest.mark.parametrize(
    "vectors",
    [
        [[float("nan")] * 8],  # NaN
        [[float("inf")] * 8],  # Inf
        [[0.5] * 8, [0.5] * 4],  # mixed dimensions
        [[0.5] * 4],  # dimension differs from the declared adapter dimension
        [[0.0] * 8],  # zero-norm vector
        [],  # cardinality mismatch
    ],
)
def test_invalid_batch_fails_to_failed_without_partial_persistence(session, vectors) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    active = make_active_version(session, workspace["brand_id"], user.id)
    document = BrandDnaDocument.model_validate(valid_document())
    derived, _ = build_chunks(active.id, document)
    malformed = MalformedEmbedding([vectors[0] * len(derived)] if vectors else vectors)
    malformed.dimensions = 8

    with pytest.raises(Exception) as excinfo:
        asyncio.run(
            service.sync_knowledge(
                session, user=user, brand_id=workspace["brand_id"],
                embedding_adapter=malformed, tracer=NOOP,
            )
        )
    # Sanitized 503 envelope at the boundary; FAILED persisted, nothing partial.
    from fastapi import HTTPException

    assert isinstance(excinfo.value, HTTPException)
    assert excinfo.value.status_code == 503
    fresh = session.get(BrandDnaVersion, active.id)
    assert fresh is not None
    assert fresh.knowledge_status == KnowledgeStatus.FAILED
    assert repository.count_chunks(session, active.id) == 0


def test_outdated_sync_is_409_without_transition(session) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    active = make_active_version(session, workspace["brand_id"], user.id)
    active.knowledge_status = KnowledgeStatus.OUTDATED
    session.commit()
    fake = FakeEmbeddingModel()

    with pytest.raises(SyncConflictError) as excinfo:
        asyncio.run(
            service.sync_knowledge(
                session, user=user, brand_id=workspace["brand_id"],
                embedding_adapter=fake, tracer=NOOP,
            )
        )
    assert excinfo.value.details["reason"] == "outdated_needs_publish"
    fresh = session.get(BrandDnaVersion, active.id)
    assert fresh is not None
    assert fresh.knowledge_status == KnowledgeStatus.OUTDATED
    assert not fake.calls  # no embedding work at all


def test_embed_failure_marks_failed_and_keeps_previous_chunks(session) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    active = make_active_version(session, workspace["brand_id"], user.id)

    ok = asyncio.run(
        service.sync_knowledge(
            session, user=user, brand_id=workspace["brand_id"],
            embedding_adapter=FakeEmbeddingModel(), tracer=NOOP,
        )
    )
    # Force regeneration so the failing adapter is actually invoked.
    active.knowledge_fingerprint = "0" * 64
    session.commit()

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            service.sync_knowledge(
                session, user=user, brand_id=workspace["brand_id"],
                embedding_adapter=FailingEmbedding(), tracer=NOOP,
            )
        )
    assert excinfo.value.status_code == 503
    fresh = session.get(BrandDnaVersion, active.id)
    assert fresh is not None
    assert fresh.knowledge_status == KnowledgeStatus.FAILED
    # Previous chunks survive intact.
    assert repository.count_chunks(session, active.id) == ok.chunk_count


def test_sync_emits_sanitized_spans_with_counts(session) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    make_active_version(session, workspace["brand_id"], user.id)
    tracer = RecordingTracer()

    result = asyncio.run(
        service.sync_knowledge(
            session, user=user, brand_id=workspace["brand_id"],
            embedding_adapter=FakeEmbeddingModel(), tracer=tracer,
        )
    )

    operations = [span.operation for span in tracer.spans]
    assert operations == ["knowledge.embed", "knowledge.sync"]
    embed_span, sync_span = tracer.spans
    assert embed_span.summary is not None and embed_span.summary.chunk_count == result.chunk_count
    assert sync_span.summary is not None and sync_span.summary.ok is True
    assert sync_span.summary.chunk_count == result.chunk_count
    # No raw payloads: chunk contents never travel in spans.
    dumped = " ".join(
        str(getattr(span.summary, "model_dump_json", lambda: "")()) for span in tracer.spans
    )
    assert "purpose" not in dumped


def test_error_spans_are_emitted_on_failure(session) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    active = make_active_version(session, workspace["brand_id"], user.id)
    tracer = RecordingTracer()

    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        asyncio.run(
            service.sync_knowledge(
                session, user=user, brand_id=workspace["brand_id"],
                embedding_adapter=FailingEmbedding(), tracer=tracer,
            )
        )
    fresh = session.get(BrandDnaVersion, active.id)
    assert fresh is not None
    assert fresh.knowledge_status == KnowledgeStatus.FAILED
    operations = [span.operation for span in tracer.spans]
    assert operations == ["knowledge.embed", "knowledge.sync"]
    assert tracer.spans[0].error == "RuntimeError"
    assert tracer.spans[1].summary is not None and tracer.spans[1].summary.ok is False


def test_concurrent_syncs_yield_exactly_one_success_and_one_conflict(tmp_path) -> None:
    from sqlalchemy.orm import Session

    from app.brand_dna.models import BrandDnaStatus, KnowledgeStatus
    from tests.conftest import make_concurrency_engine, seed_race_workspace

    engine = make_concurrency_engine(tmp_path)
    brand_id, token = seed_race_workspace(engine)
    with Session(engine) as seed:
        profile_id = uuid.UUID(_sub_from_token(token))
        active = BrandDnaVersion(
            id=uuid.uuid4(), brand_id=brand_id, version=1,
            status=BrandDnaStatus.ACTIVE, document=valid_document(),
            created_by=profile_id, knowledge_status=KnowledgeStatus.NOT_SYNCED,
        )
        seed.add(active)
        seed.commit()
        version_id = active.id
    user = AuthenticatedUser(id=uuid.UUID(_sub_from_token(token)), email=None)
    fake = YieldingEmbedding()

    async def scenario() -> tuple[Any, Any]:
        async def run_one() -> Any:
            async with _session_ctx(engine) as s:
                return await service.sync_knowledge(
                    s, user=user, brand_id=brand_id,
                    embedding_adapter=fake, tracer=NOOP,
                )

        return await asyncio.gather(run_one(), run_one(), return_exceptions=True)

    first, second = asyncio.run(scenario())
    outcomes = sorted(
        ["ok" if not isinstance(r, Exception) else type(r).__name__ for r in (first, second)]
    )
    assert outcomes == ["SyncConflictError", "ok"]
    with Session(engine) as check:
        fresh = check.get(BrandDnaVersion, version_id)
        assert fresh is not None
        assert fresh.knowledge_status == KnowledgeStatus.SYNCED
        assert repository.count_chunks(check, version_id) == expected_chunk_count(version_id)


def _sub_from_token(token: str) -> str:
    import jwt as pyjwt

    return str(pyjwt.decode(token, options={"verify_signature": False})["sub"])


class _session_ctx:
    def __init__(self, engine) -> None:
        self.engine = engine

    async def __aenter__(self) -> Session:
        self.session = Session(self.engine)
        return self.session

    async def __aexit__(self, *args: Any) -> None:
        self.session.close()


# --- 6.2: KnowledgeNotAvailableError has no HTTP mapping in this change ---


def test_knowledge_not_available_maps_to_503_at_the_app_boundary() -> None:
    # 006 kept KnowledgeNotAvailableError handler-free (internal consumers only);
    # spec 04 registers the app-level envelope mapping: 503 KNOWLEDGE_NOT_AVAILABLE.
    from app.main import app

    assert KnowledgeNotAvailableError in app.exception_handlers


# --- 7.1: build_context ---


def sync_for_context(session, brand_id: uuid.UUID, user: AuthenticatedUser) -> Any:
    return asyncio.run(
        service.sync_knowledge(
            session, user=user, brand_id=brand_id,
            embedding_adapter=FakeEmbeddingModel(), tracer=NOOP,
        )
    )


def test_mandatory_always_included_regardless_of_similarity(session) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    make_active_version(session, workspace["brand_id"], user.id)
    sync_for_context(session, workspace["brand_id"], user)

    context = asyncio.run(
        service.build_context(
            session, brand_id=workspace["brand_id"], task="TEXT", query="anything unrelated",
            embedding_adapter=FakeEmbeddingModel(), tracer=NOOP,
        )
    )
    mandatory_rules = {rule.rule_type for rule in context.mandatory}
    assert {"avoid_vocabulary", "dont_example", "communication_rule", "restriction"} <= (
        mandatory_rules
    )
    # VISUAL-only mandatory (logo_usage) is excluded from a TEXT task.
    assert "logo_usage" not in mandatory_rules


def test_topk_is_isolated_by_brand_and_version(session) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    active = make_active_version(session, workspace["brand_id"], user.id)
    sync_for_context(session, workspace["brand_id"], user)
    other_brand, other_version = uuid.uuid4(), uuid.uuid4()
    seed_foreign_chunks(session, other_brand, other_version)

    context = asyncio.run(
        service.build_context(
            session, brand_id=workspace["brand_id"], task="TEXT", query="quinoa snacks",
            embedding_adapter=FakeEmbeddingModel(), tracer=NOOP, top_k=20,
        )
    )
    derived_ids = {c.id for c in build_chunks(active.id, _doc())[0]}
    foreign_ids = {c.id for c in build_chunks(other_version, _doc())[0]}
    returned = {r.id for r in context.mandatory} | {r.id for r in context.semantic}
    assert returned <= derived_ids
    assert returned.isdisjoint(foreign_ids)


def seed_foreign_chunks(session, brand_id: uuid.UUID, version_id: uuid.UUID) -> None:
    chunks, _ = build_chunks(version_id, _doc())
    repository.replace_version_chunks(
        session, brand_id=brand_id, brand_dna_version_id=version_id,
        chunks=chunks, embeddings=[[0.5] * 8] * len(chunks),
    )
    session.commit()


def _doc() -> BrandDnaDocument:
    return BrandDnaDocument.model_validate(valid_document())


def test_segmentation_by_task_scope(session) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    make_active_version(session, workspace["brand_id"], user.id)
    sync_for_context(session, workspace["brand_id"], user)

    text_context = asyncio.run(
        service.build_context(
            session, brand_id=workspace["brand_id"], task="TEXT", query="quinoa",
            embedding_adapter=FakeEmbeddingModel(), tracer=NOOP, top_k=20,
        )
    )
    visual_context = asyncio.run(
        service.build_context(
            session, brand_id=workspace["brand_id"], task="VISUAL", query="packaging",
            embedding_adapter=FakeEmbeddingModel(), tracer=NOOP, top_k=20,
        )
    )

    def scopes(rules: list[service.KnowledgeRule]) -> set[KnowledgeScope]:
        return {rule.scope for rule in rules}

    assert scopes(text_context.semantic) <= {KnowledgeScope.TEXT, KnowledgeScope.BOTH}
    assert scopes(visual_context.semantic) <= {KnowledgeScope.VISUAL, KnowledgeScope.BOTH}
    # BOTH mandatory rules are shared by both tasks.
    assert scopes(text_context.mandatory) >= {KnowledgeScope.BOTH}
    assert scopes(visual_context.mandatory) >= {KnowledgeScope.BOTH}


@pytest.mark.parametrize(
    "state",
    [KnowledgeStatus.NOT_SYNCED, KnowledgeStatus.SYNCING, KnowledgeStatus.FAILED],
)
def test_fail_safe_on_non_servable_state(session, state) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    make_active_version(session, workspace["brand_id"], user.id, knowledge_status=state)

    with pytest.raises(KnowledgeNotAvailableError):
        asyncio.run(
            service.build_context(
                session, brand_id=workspace["brand_id"], task="TEXT", query="q",
                embedding_adapter=FakeEmbeddingModel(), tracer=NOOP,
            )
        )


def test_fail_safe_without_active_version(session) -> None:
    workspace = make_workspace(session)

    with pytest.raises(KnowledgeNotAvailableError):
        asyncio.run(
            service.build_context(
                session, brand_id=workspace["brand_id"], task="TEXT", query="q",
                embedding_adapter=FakeEmbeddingModel(), tracer=NOOP,
            )
        )


def test_fail_safe_without_applicable_mandatory(session) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    active = make_active_version(session, workspace["brand_id"], user.id)
    sync_for_context(session, workspace["brand_id"], user)
    # Corrupt: strip every mandatory chunk (a valid document always has them).
    from sqlalchemy import delete

    session.execute(
        delete(repository.BrandKnowledgeChunk).where(
            repository.BrandKnowledgeChunk.brand_dna_version_id == active.id,
            repository.BrandKnowledgeChunk.mandatory.is_(True),
        )
    )
    session.commit()

    with pytest.raises(KnowledgeNotAvailableError):
        asyncio.run(
            service.build_context(
                session, brand_id=workspace["brand_id"], task="TEXT", query="q",
                embedding_adapter=FakeEmbeddingModel(), tracer=NOOP,
            )
        )


def test_fail_safe_with_missing_query_adapter(session) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    make_active_version(session, workspace["brand_id"], user.id)
    sync_for_context(session, workspace["brand_id"], user)

    with pytest.raises(KnowledgeNotAvailableError):
        asyncio.run(
            service.build_context(
                session, brand_id=workspace["brand_id"], task="TEXT", query="q",
                embedding_adapter=None, tracer=NOOP,
            )
        )


def test_fail_safe_on_vector_space_mismatch(session) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    active = make_active_version(session, workspace["brand_id"], user.id)
    sync_for_context(session, workspace["brand_id"], user)

    # Different model name, same declared dimensions.
    class RenamedFake(FakeEmbeddingModel):
        name = "renamed-embedding"

    with pytest.raises(KnowledgeNotAvailableError):
        asyncio.run(
            service.build_context(
                session, brand_id=workspace["brand_id"], task="TEXT", query="q",
                embedding_adapter=RenamedFake(), tracer=NOOP,
            )
        )
    # Different dimensions.
    with pytest.raises(KnowledgeNotAvailableError):
        asyncio.run(
            service.build_context(
                session, brand_id=workspace["brand_id"], task="TEXT", query="q",
                embedding_adapter=OtherDimEmbedding(), tracer=NOOP,
            )
        )
    # NULL evidence in a servable state is corruption.
    active.knowledge_embedding_model = None
    session.commit()
    with pytest.raises(KnowledgeNotAvailableError):
        asyncio.run(
            service.build_context(
                session, brand_id=workspace["brand_id"], task="TEXT", query="q",
                embedding_adapter=FakeEmbeddingModel(), tracer=NOOP,
            )
        )


@pytest.mark.parametrize(
    "vectors",
    [
        [],  # zero vectors
        [[0.5] * 8, [0.5] * 8],  # more than one
        [[float("nan")] * 8],  # non-finite
        [[0.0] * 8],  # zero norm
        [[0.5] * 4],  # wrong dimension
    ],
)
def test_fail_safe_on_malformed_query_vector(session, vectors) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    make_active_version(session, workspace["brand_id"], user.id)
    sync_for_context(session, workspace["brand_id"], user)

    class QueryFake(MalformedEmbedding):
        name = FakeEmbeddingModel.name
        dimensions = FakeEmbeddingModel.dimensions

    fake = QueryFake(vectors)

    with pytest.raises(KnowledgeNotAvailableError):
        asyncio.run(
            service.build_context(
                session, brand_id=workspace["brand_id"], task="TEXT", query="q",
                embedding_adapter=fake, tracer=NOOP,
            )
        )


def test_fail_safe_when_query_adapter_fails(session) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    make_active_version(session, workspace["brand_id"], user.id)
    sync_for_context(session, workspace["brand_id"], user)

    with pytest.raises(KnowledgeNotAvailableError):
        asyncio.run(
            service.build_context(
                session, brand_id=workspace["brand_id"], task="TEXT", query="q",
                embedding_adapter=FailingEmbedding(), tracer=NOOP,
            )
        )


def test_outdated_version_is_servable(session) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    active = make_active_version(session, workspace["brand_id"], user.id)
    sync_for_context(session, workspace["brand_id"], user)
    # Brand DNA marks SYNCED -> OUTDATED on draft edits; still servable.
    active.knowledge_status = KnowledgeStatus.OUTDATED
    session.commit()

    context = asyncio.run(
        service.build_context(
            session, brand_id=workspace["brand_id"], task="VISUAL", query="packaging",
            embedding_adapter=FakeEmbeddingModel(), tracer=NOOP,
        )
    )
    assert context.mandatory
    assert {rule.rule_type for rule in context.mandatory} >= {"logo_usage", "restriction"}


def test_build_context_is_stable_and_emits_retrieve_span(session) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    make_active_version(session, workspace["brand_id"], user.id)
    sync_for_context(session, workspace["brand_id"], user)
    tracer = RecordingTracer()

    first = asyncio.run(
        service.build_context(
            session, brand_id=workspace["brand_id"], task="TEXT", query="quinoa",
            embedding_adapter=FakeEmbeddingModel(), tracer=tracer,
        )
    )
    second = asyncio.run(
        service.build_context(
            session, brand_id=workspace["brand_id"], task="TEXT", query="quinoa",
            embedding_adapter=FakeEmbeddingModel(), tracer=NOOP,
        )
    )

    assert [r.id for r in first.mandatory] == [r.id for r in second.mandatory]
    assert [r.id for r in first.semantic] == [r.id for r in second.semantic]
    assert len(tracer.spans) == 1
    span = tracer.spans[0]
    assert span.operation == "knowledge.retrieve"
    assert span.summary is not None
    assert span.summary.mandatory_count == len(first.mandatory)
    assert span.summary.semantic_count == len(first.semantic)


def test_top_k_is_clamped_to_bounds(session) -> None:
    workspace = make_workspace(session)
    user = make_user(workspace, BrandRole.CREATOR)
    make_active_version(session, workspace["brand_id"], user.id)
    sync_for_context(session, workspace["brand_id"], user)

    huge = asyncio.run(
        service.build_context(
            session, brand_id=workspace["brand_id"], task="TEXT", query="quinoa",
            embedding_adapter=FakeEmbeddingModel(), tracer=NOOP, top_k=999,
        )
    )
    zero = asyncio.run(
        service.build_context(
            session, brand_id=workspace["brand_id"], task="TEXT", query="quinoa",
            embedding_adapter=FakeEmbeddingModel(), tracer=NOOP, top_k=0,
        )
    )
    assert len(huge.semantic) <= 20
    assert zero.semantic  # clamped to 1, not empty
