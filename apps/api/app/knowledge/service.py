"""Application service for knowledge: explicit sync with an atomic claim and
the fail-safe hybrid context builder.

Sync machine (design.md): validations first (membership/role -> ACTIVE -> adapter
presence), deterministic chunking + fingerprint BEFORE the claim (pure CPU),
short committed conditional UPDATE (no lock/transaction across the provider
`await`), batch validation, transactional finalization (delete+insert + SYNCED +
evidence), and FAILED persisted in a separate transaction with previous chunks
intact. `OUTDATED` is only cleared by Brand DNA "publish changes".
"""

import logging
import math
import time
import uuid
from dataclasses import dataclass
from typing import Any, Literal, cast

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.ai.contracts import TraceSummary
from app.ai.errors import AIProviderNotConfiguredError
from app.ai.ports import EmbeddingModel
from app.brand_dna.models import BrandDnaStatus, BrandDnaVersion, KnowledgeStatus
from app.brand_dna.schemas import BrandDnaDocument
from app.identity.auth import AuthenticatedUser
from app.knowledge import chunker, policies, repository
from app.knowledge.errors import KnowledgeNotAvailableError, SyncConflictError
from app.knowledge.models import KnowledgeScope
from app.knowledge.schemas import (
    KnowledgeChunksOut,
    KnowledgeStatusOut,
    VersionRef,
)
from app.observability.ports import CapabilitySpan, Tracer

logger = logging.getLogger(__name__)

SERVABLE_STATUSES = (KnowledgeStatus.SYNCED, KnowledgeStatus.OUTDATED)
TASK_SCOPES: dict[str, list[KnowledgeScope]] = {
    "TEXT": [KnowledgeScope.TEXT, KnowledgeScope.BOTH],
    "VISUAL": [KnowledgeScope.VISUAL, KnowledgeScope.BOTH],
}
MIN_TOP_K, MAX_TOP_K = 1, 20


@dataclass(frozen=True, slots=True)
class KnowledgeRule:
    """A retrievable rule with its stable chunk id (consumers persist these)."""

    id: uuid.UUID
    section: str
    rule_type: str
    scope: KnowledgeScope
    content: str


@dataclass(frozen=True, slots=True)
class BuiltContext:
    brand_dna_version_id: uuid.UUID
    mandatory: list[KnowledgeRule]
    semantic: list[KnowledgeRule]


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Active Brand DNA version not found"
    )


async def _emit(tracer: Tracer, span: CapabilitySpan) -> None:
    """Emit one span; tracer failures degrade to a sanitized warning (never propagate)."""
    try:
        await tracer.emit_span(span)
    except Exception as exc:
        logger.warning("Tracer failed while emitting span: %s", type(exc).__name__)


def _resolve_reader_membership(session: Session, user: AuthenticatedUser, brand_id: uuid.UUID):
    membership = repository.get_membership(session, user.id, brand_id)
    # 403 before evaluating any brand resource, even its existence (design matrix).
    policies.require_reader(membership)
    return membership


def _require_active(session: Session, brand_id: uuid.UUID) -> BrandDnaVersion:
    active = (
        session.execute(
            select(BrandDnaVersion).where(
                BrandDnaVersion.brand_id == brand_id,
                BrandDnaVersion.status == BrandDnaStatus.ACTIVE,
            )
        )
        .scalars()
        .first()
    )
    if active is None:
        raise _not_found()
    return active


def _has_evidence_mismatch(
    version: BrandDnaVersion, model: str, dimensions: int, fingerprint: str
) -> bool:
    return (
        version.knowledge_embedding_model != model
        or version.knowledge_embedding_dimensions != dimensions
        or version.knowledge_fingerprint != fingerprint
    )


def _claim_syncing(
    session: Session, version_id: uuid.UUID, model: str, dimensions: int, fingerprint: str
) -> bool:
    """Conditional atomic claim in a short transaction, committed immediately.

    Sources: NOT_SYNCED|FAILED, or SYNCED with model/dimension/fingerprint
    mismatch (regeneration of derived data). `rowcount == 1` means the claim was
    won; this UPDATE is the serialization point for concurrent syncs.
    """
    result = cast("CursorResult[Any]", session.execute(
        update(BrandDnaVersion)
        .where(
            BrandDnaVersion.id == version_id,
            BrandDnaVersion.status == BrandDnaStatus.ACTIVE,
            or_(
                BrandDnaVersion.knowledge_status.in_(
                    [KnowledgeStatus.NOT_SYNCED, KnowledgeStatus.FAILED]
                ),
                and_(
                    BrandDnaVersion.knowledge_status == KnowledgeStatus.SYNCED,
                    or_(
                        BrandDnaVersion.knowledge_embedding_model.is_distinct_from(model),
                        BrandDnaVersion.knowledge_embedding_dimensions.is_distinct_from(
                            dimensions
                        ),
                        BrandDnaVersion.knowledge_fingerprint.is_distinct_from(fingerprint),
                    ),
                ),
            ),
        )
        .values(knowledge_status=KnowledgeStatus.SYNCING)
    ))
    session.commit()
    return result.rowcount == 1


def _validate_batch(vectors: list[list[float]], *, expected: int, dimensions: int) -> None:
    if len(vectors) != expected:
        raise ValueError("embedding batch cardinality mismatch")
    seen_dimension: int | None = None
    for vector in vectors:
        if not vector:
            raise ValueError("empty embedding vector")
        if any(not math.isfinite(x) for x in vector):
            raise ValueError("non-finite embedding value")
        if seen_dimension is None:
            seen_dimension = len(vector)
        elif len(vector) != seen_dimension:
            raise ValueError("mixed embedding dimensions in batch")
        if math.sqrt(sum(x * x for x in vector)) <= 0.0:
            raise ValueError("zero-norm embedding vector")
    if seen_dimension != dimensions:
        raise ValueError("embedding dimension differs from the declared adapter dimension")


def _status_out(version: BrandDnaVersion, chunk_count: int | None) -> KnowledgeStatusOut:
    synced = version.knowledge_embedding_model is not None
    return KnowledgeStatusOut(
        brand_dna_version_id=version.id,
        version=version.version,
        knowledge_status=version.knowledge_status,
        chunk_count=chunk_count if synced else None,
        embedding_model=version.knowledge_embedding_model,
    )


def get_knowledge(
    session: Session, user: AuthenticatedUser, brand_id: uuid.UUID
) -> KnowledgeChunksOut:
    """Published chunks of the ACTIVE version (no embeddings) for any member."""
    _resolve_reader_membership(session, user, brand_id)
    active = _require_active(session, brand_id)
    chunks = repository.list_chunks(
        session, brand_id=brand_id, brand_dna_version_id=active.id
    )
    return KnowledgeChunksOut(
        brand_dna_version=VersionRef(
            id=active.id, version=active.version, knowledge_status=active.knowledge_status
        ),
        chunks=chunks,
    )


def get_status(
    session: Session, user: AuthenticatedUser, brand_id: uuid.UUID
) -> KnowledgeStatusOut:
    _resolve_reader_membership(session, user, brand_id)
    active = _require_active(session, brand_id)
    count = (
        repository.count_chunks(session, active.id)
        if active.knowledge_embedding_model is not None
        else None
    )
    return _status_out(active, count)


def _conflict(reason: str, version_id: uuid.UUID) -> SyncConflictError:
    if reason == "outdated_needs_publish":
        return SyncConflictError(
            "Knowledge is OUTDATED: publish the pending draft changes before syncing",
            reason=reason,
            version_id=version_id,
        )
    return SyncConflictError(
        "A knowledge sync is already in progress for this version",
        reason=reason,
        version_id=version_id,
    )


async def sync_knowledge(
    session: Session,
    *,
    user: AuthenticatedUser,
    brand_id: uuid.UUID,
    embedding_adapter: EmbeddingModel | None,
    tracer: Tracer,
) -> KnowledgeStatusOut:
    """Explicit sync of the ACTIVE version's knowledge (CREATOR only)."""
    membership = repository.get_membership(session, user.id, brand_id)
    policies.require_sync_creator(membership)
    active = _require_active(session, brand_id)
    if embedding_adapter is None:
        # Before any mutation: 503 with no state transition.
        raise AIProviderNotConfiguredError("knowledge.sync")

    # Deterministic chunking + expected evidence, before the claim and any await.
    document = BrandDnaDocument.model_validate(active.document)
    chunks, fingerprint = chunker.build_chunks(active.id, document)
    model, dimensions = embedding_adapter.name, embedding_adapter.dimensions
    entity = f"brand_knowledge:{active.id}"

    if not _claim_syncing(session, active.id, model, dimensions, fingerprint):
        # Fresh read after the lost claim: idempotent / concurrent / outdated.
        session.rollback()
        fresh = session.get(BrandDnaVersion, active.id)
        assert fresh is not None
        if fresh.knowledge_status == KnowledgeStatus.SYNCED and not _has_evidence_mismatch(
            fresh, model, dimensions, fingerprint
        ):
            count = repository.count_chunks(session, fresh.id)
            await _emit(
                tracer,
                CapabilitySpan(
                    entity=entity, model=model, latency_ms=0.0, operation="knowledge.sync",
                    summary=TraceSummary(
                        contract="KnowledgeSync", ok=True, chunk_count=count
                    ),
                ),
            )
            return _status_out(fresh, count)
        if fresh.knowledge_status == KnowledgeStatus.OUTDATED:
            raise _conflict("outdated_needs_publish", fresh.id)
        if fresh.knowledge_status == KnowledgeStatus.SYNCING:
            raise _conflict("sync_in_progress", fresh.id)
        raise _conflict("state_changed", fresh.id)

    start = time.perf_counter()
    try:
        # Provider call with NO open transaction or lock (claim was committed).
        embed_start = time.perf_counter()
        try:
            vectors = await embedding_adapter.embed([chunk.content for chunk in chunks])
        except Exception as exc:
            await _emit(
                tracer,
                CapabilitySpan(
                    entity=entity, model=model,
                    latency_ms=(time.perf_counter() - embed_start) * 1000.0,
                    operation="knowledge.embed",
                    summary=TraceSummary(
                        contract="KnowledgeEmbed", ok=False, chunk_count=len(chunks)
                    ),
                    error=type(exc).__name__,
                ),
            )
            raise
        await _emit(
            tracer,
            CapabilitySpan(
                entity=entity, model=model,
                latency_ms=(time.perf_counter() - embed_start) * 1000.0,
                operation="knowledge.embed",
                summary=TraceSummary(
                    contract="KnowledgeEmbed", ok=True, chunk_count=len(chunks)
                ),
            ),
        )
        _validate_batch(vectors, expected=len(chunks), dimensions=dimensions)

        # Finalization (transaction #2): atomic replace + SYNCED + evidence.
        finalized = cast("CursorResult[Any]", session.execute(
            update(BrandDnaVersion)
            .where(
                BrandDnaVersion.id == active.id,
                BrandDnaVersion.knowledge_status == KnowledgeStatus.SYNCING,
            )
            .values(
                knowledge_status=KnowledgeStatus.SYNCED,
                knowledge_embedding_model=model,
                knowledge_embedding_dimensions=dimensions,
                knowledge_fingerprint=fingerprint,
            )
        ))
        if finalized.rowcount != 1:
            session.rollback()
            raise _conflict("state_changed", active.id)
        repository.replace_version_chunks(
            session,
            brand_id=brand_id,
            brand_dna_version_id=active.id,
            chunks=chunks,
            embeddings=vectors,
        )
        session.commit()
    except Exception as exc:
        # Failure (transaction #3, only when claimed): FAILED in a separate
        # transaction; previous chunks survive intact.
        session.rollback()
        session.execute(
            update(BrandDnaVersion)
            .where(
                BrandDnaVersion.id == active.id,
                BrandDnaVersion.knowledge_status == KnowledgeStatus.SYNCING,
            )
            .values(knowledge_status=KnowledgeStatus.FAILED)
        )
        session.commit()
        await _emit(
            tracer,
            CapabilitySpan(
                entity=entity, model=model,
                latency_ms=(time.perf_counter() - start) * 1000.0,
                operation="knowledge.sync",
                summary=TraceSummary(contract="KnowledgeSync", ok=False, chunk_count=0),
                error=type(exc).__name__,
            ),
        )
        if isinstance(exc, SyncConflictError):
            raise
        # Sanitized 503: no provider/exception content.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge sync failed; retry is available",
        ) from exc

    session.expire_all()
    fresh = session.get(BrandDnaVersion, active.id)
    assert fresh is not None
    count = repository.count_chunks(session, active.id)
    await _emit(
        tracer,
        CapabilitySpan(
            entity=entity, model=model, latency_ms=(time.perf_counter() - start) * 1000.0,
            operation="knowledge.sync",
            summary=TraceSummary(contract="KnowledgeSync", ok=True, chunk_count=count),
        ),
    )
    return _status_out(fresh, count)


async def build_context(
    session: Session,
    *,
    brand_id: uuid.UUID,
    task: Literal["TEXT", "VISUAL"],
    query: str,
    embedding_adapter: EmbeddingModel | None,
    tracer: Tracer,
    top_k: int = 8,
) -> BuiltContext:
    """Hybrid fail-safe context: mandatory always present + semantic top-k.

    Raises `KnowledgeNotAvailableError` (never partial context) when the
    adapter is absent, there is no ACTIVE version, its status is not servable
    (SYNCED|OUTDATED), the persisted vector space mismatches the query adapter,
    no mandatory rule applies, or the query embedding is invalid.
    """
    start = time.perf_counter()
    if embedding_adapter is None:
        raise KnowledgeNotAvailableError("Embedding adapter is not configured")
    active = session.execute(
        select(BrandDnaVersion).where(
            BrandDnaVersion.brand_id == brand_id,
            BrandDnaVersion.status == BrandDnaStatus.ACTIVE,
        )
    ).scalars().first()
    if active is None:
        raise KnowledgeNotAvailableError("No active Brand DNA version")
    if active.knowledge_status not in SERVABLE_STATUSES:
        raise KnowledgeNotAvailableError("Knowledge is not in a servable state")
    # Vector-space compatibility before ranking: persisted vectors must belong
    # to the querying adapter's space (NULL evidence in a servable state is
    # corruption).
    if (
        active.knowledge_embedding_model is None
        or active.knowledge_embedding_dimensions is None
        or active.knowledge_embedding_model != embedding_adapter.name
        or active.knowledge_embedding_dimensions != embedding_adapter.dimensions
    ):
        raise KnowledgeNotAvailableError(
            "Persisted embeddings belong to a different vector space; re-sync required"
        )

    scopes = TASK_SCOPES[task]
    mandatory_rows = repository.list_chunks(
        session,
        brand_id=brand_id,
        brand_dna_version_id=active.id,
        mandatory=True,
        scopes=scopes,
    )
    if not mandatory_rows:
        # A valid published document always carries applicable mandatory rules;
        # empty means incomplete/corrupt knowledge -> fail safe.
        raise KnowledgeNotAvailableError("No mandatory rules apply to this task scope")

    try:
        query_vectors = await embedding_adapter.embed([query])
    except Exception as exc:
        raise KnowledgeNotAvailableError("Query embedding failed") from exc
    try:
        _validate_batch(query_vectors, expected=1, dimensions=embedding_adapter.dimensions)
    except ValueError as exc:
        raise KnowledgeNotAvailableError("Query embedding is invalid") from exc

    ranked = repository.rank_semantic(
        session,
        brand_id=brand_id,
        brand_dna_version_id=active.id,
        scopes=scopes,
        query_vector=query_vectors[0],
        top_k=min(max(top_k, MIN_TOP_K), MAX_TOP_K),
    )
    context = BuiltContext(
        brand_dna_version_id=active.id,
        mandatory=[
            KnowledgeRule(
                id=row.id, section=row.section, rule_type=row.rule_type,
                scope=row.scope, content=row.content,
            )
            for row in mandatory_rows
        ],
        semantic=[
            KnowledgeRule(
                id=row.id, section=row.section, rule_type=row.rule_type,
                scope=row.scope, content=row.content,
            )
            for row in ranked
        ],
    )
    await _emit(
        tracer,
        CapabilitySpan(
            entity=f"brand_knowledge:{active.id}", model=embedding_adapter.name,
            latency_ms=(time.perf_counter() - start) * 1000.0,
            operation="knowledge.retrieve",
            summary=TraceSummary(
                contract="KnowledgeRetrieval", ok=True,
                mandatory_count=len(context.mandatory), semantic_count=len(context.semantic),
            ),
        ),
    )
    return context
