"""Repository for Brand Knowledge persistence. All SQL lives here.

Ranking is dual-dialect by design: PostgreSQL uses the canonical pgvector
`<=>` cosine distance in SQL; SQLite (dev/test seam) computes cosine distance
in Python. Both branches share the total order (distance ASC, id ASC) so exact
ties resolve identically. The SQLite branch is a test seam, not a simulation of
production vector search.
"""

import math
import uuid
from dataclasses import dataclass

from sqlalchemy import TextClause, bindparam, delete, func, select, text
from sqlalchemy.orm import Session

from app.identity import repository as identity_repository
from app.identity.models import BrandMembership
from app.knowledge.chunker import Chunk
from app.knowledge.models import BrandKnowledgeChunk, KnowledgeScope


@dataclass(frozen=True, slots=True)
class RankedChunk:
    """A chunk with its cosine distance to the query vector."""

    id: uuid.UUID
    section: str
    rule_type: str
    scope: KnowledgeScope
    content: str
    distance: float


def get_membership(
    session: Session, profile_id: uuid.UUID, brand_id: uuid.UUID
) -> BrandMembership | None:
    return identity_repository.get_membership(session, profile_id, brand_id)


def list_chunks(
    session: Session,
    *,
    brand_id: uuid.UUID,
    brand_dna_version_id: uuid.UUID,
    mandatory: bool | None = None,
    scopes: list[KnowledgeScope] | None = None,
) -> list[BrandKnowledgeChunk]:
    stmt = select(BrandKnowledgeChunk).where(
        BrandKnowledgeChunk.brand_id == brand_id,
        BrandKnowledgeChunk.brand_dna_version_id == brand_dna_version_id,
    )
    if mandatory is not None:
        stmt = stmt.where(BrandKnowledgeChunk.mandatory == mandatory)
    if scopes is not None:
        stmt = stmt.where(BrandKnowledgeChunk.scope.in_(scopes))
    stmt = stmt.order_by(BrandKnowledgeChunk.id.asc())
    return list(session.scalars(stmt))


def count_chunks(session: Session, brand_dna_version_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(BrandKnowledgeChunk).where(
        BrandKnowledgeChunk.brand_dna_version_id == brand_dna_version_id
    )
    return int(session.scalar(stmt) or 0)


def replace_version_chunks(
    session: Session,
    *,
    brand_id: uuid.UUID,
    brand_dna_version_id: uuid.UUID,
    chunks: list[Chunk],
    embeddings: list[list[float]],
) -> None:
    """Atomic replace per version (delete+insert) preserving the stable UUIDv5 ids.

    Caller owns the transaction: this runs inside the sync finalization.
    """
    session.execute(
        delete(BrandKnowledgeChunk).where(
            BrandKnowledgeChunk.brand_dna_version_id == brand_dna_version_id
        )
    )
    session.add_all(
        BrandKnowledgeChunk(
            id=chunk.id,
            brand_id=brand_id,
            brand_dna_version_id=brand_dna_version_id,
            section=chunk.section,
            rule_type=chunk.rule_type,
            scope=chunk.scope,
            mandatory=chunk.mandatory,
            content=chunk.content,
            chunk_metadata=dict(chunk.metadata),
            embedding=embedding,
        )
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    )


def _cosine_distance(query: list[float], vector: list[float]) -> float:
    dot = sum(a * b for a, b in zip(query, vector, strict=True))
    norm_q = math.sqrt(sum(a * a for a in query))
    norm_v = math.sqrt(sum(b * b for b in vector))
    return 1.0 - dot / (norm_q * norm_v)


def rank_semantic(
    session: Session,
    *,
    brand_id: uuid.UUID,
    brand_dna_version_id: uuid.UUID,
    scopes: list[KnowledgeScope],
    query_vector: list[float],
    top_k: int,
) -> list[RankedChunk]:
    """Rank non-mandatory chunks of the scope by cosine distance to the query.

    Filtering by brand+version happens strictly before any ranking; ties break
    by chunk id ASC in both dialects (total order).
    """
    if session.bind is None:
        raise RuntimeError("repository requires a bound session")
    if session.bind.dialect.name == "postgresql":
        return _rank_pg(
            session,
            brand_id=brand_id,
            brand_dna_version_id=brand_dna_version_id,
            scopes=scopes,
            query_vector=query_vector,
            top_k=top_k,
        )
    # SQLite seam: Python cosine over the filtered candidates.
    candidates = list_chunks(
        session,
        brand_id=brand_id,
        brand_dna_version_id=brand_dna_version_id,
        mandatory=False,
        scopes=scopes,
    )
    scored = [
        RankedChunk(
            id=c.id,
            section=c.section,
            rule_type=c.rule_type,
            scope=c.scope,
            content=c.content,
            distance=_cosine_distance(query_vector, c.embedding),
        )
        for c in candidates
        if c.embedding is not None
    ]
    scored.sort(key=lambda ranked: (ranked.distance, ranked.id))
    return scored[:top_k]


def _rank_semantic_sql(
    *,
    brand_id: uuid.UUID,
    brand_dna_version_id: uuid.UUID,
    scopes: list[KnowledgeScope],
    query_vector: list[float],
    top_k: int,
) -> TextClause:
    """PostgreSQL semantic ranking statement (pgvector cosine distance).

    `scopes` MUST use an expanding bindparam: a plain tuple binding would send
    a single tuple parameter to `IN :scopes`, which PostgreSQL cannot compare
    against the `knowledge_scope` enum. The comparison casts the column to
    `text` (`scope::text IN :scopes`) rather than relying on implicit
    enum/varchar coercion: psycopg3 declares expanding string bindparams with
    an explicit `::VARCHAR` type in the parameterized statement it sends the
    server, which suppresses Postgres's usual unknown-literal-to-enum
    coercion and raises `operator does not exist: knowledge_scope =
    character varying` (verified against a real Supabase/pgvector database;
    the SQLite test seam never exercises this branch).
    """
    return text(
        """
        SELECT id, section, rule_type, scope, mandatory, content,
               embedding <=> CAST(:query AS vector) AS distance
        FROM brand_knowledge_chunks
        WHERE brand_id = :brand_id
          AND brand_dna_version_id = :version_id
          AND mandatory = false
          AND scope::text IN :scopes
        ORDER BY distance ASC, id ASC
        LIMIT :top_k
        """
    ).bindparams(
        bindparam("scopes", [scope.value for scope in scopes], expanding=True),
        query="[" + ",".join(repr(float(x)) for x in query_vector) + "]",
        brand_id=brand_id,
        version_id=brand_dna_version_id,
        top_k=top_k,
    )


def _rank_pg(
    session: Session,
    *,
    brand_id: uuid.UUID,
    brand_dna_version_id: uuid.UUID,
    scopes: list[KnowledgeScope],
    query_vector: list[float],
    top_k: int,
) -> list[RankedChunk]:
    sql = _rank_semantic_sql(
        brand_id=brand_id,
        brand_dna_version_id=brand_dna_version_id,
        scopes=scopes,
        query_vector=query_vector,
        top_k=top_k,
    )
    rows = session.execute(sql).mappings().all()
    return [
        RankedChunk(
            id=row["id"],
            section=row["section"],
            rule_type=row["rule_type"],
            scope=KnowledgeScope(row["scope"]),
            content=row["content"],
            distance=float(row["distance"]),
        )
        for row in rows
    ]
