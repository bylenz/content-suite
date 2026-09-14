"""ORM model for Brand Knowledge chunks (DATA_MODEL.md `brand_knowledge_chunks`).

Chunks are derived, replaceable data: the published Brand DNA document is the
canonical source of truth. `id` is the deterministic UUIDv5 assigned by the
chunker (stable across re-syncs of the same version).
"""

import enum
import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator, UserDefinedType

from app.db import Base


class KnowledgeScope(enum.StrEnum):
    TEXT = "TEXT"
    VISUAL = "VISUAL"
    BOTH = "BOTH"


class _PgVector(UserDefinedType):
    """Native pgvector column type without the pgvector Python package.

    Emits `VECTOR` DDL with no fixed typmod (the dimension stays decoupled
    from the embedding model, mirroring the migration) and carries values in
    the pgvector literal text form `'[0.1,0.2]'`, which PostgreSQL casts to
    vector on write and parses back on read.
    """

    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        return "VECTOR"

    def bind_processor(self, dialect: Any) -> Any:
        def process(value: list[float] | None) -> str | None:
            if value is None:
                return None
            return "[" + ",".join(repr(float(x)) for x in value) + "]"

        return process

    def result_processor(self, dialect: Any, coltype: Any) -> Any:
        def process(value: Any) -> list[float] | None:
            if value is None:
                return None
            return [float(x) for x in json.loads(str(value))]

        return process


class Embedding(TypeDecorator[list[float]]):
    """Dual-dialect embedding storage (design.md).

    - PostgreSQL: `_PgVector` — the migration creates the native `vector`
      column; writes travel as pgvector literal text, not VARCHAR binds.
    - SQLite (dev/test seam): a JSON column with the list of floats; the
      repository ranks in Python.
    """

    impl = String  # only a compile fallback; load_dialect_impl resolves per dialect
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(_PgVector())
        return dialect.type_descriptor(JSON())


class BrandKnowledgeChunk(Base):
    __tablename__ = "brand_knowledge_chunks"
    __table_args__ = (
        Index("ix_brand_knowledge_chunks_brand_version", "brand_id", "brand_dna_version_id"),
        # Partial mandatory index per version: the mandatory lookups of the context builder.
        Index(
            "ix_brand_knowledge_chunks_mandatory_per_version",
            "brand_dna_version_id",
            sqlite_where=text("mandatory = 1"),
            postgresql_where=text("mandatory IS TRUE"),
        ),
        Index("ix_brand_knowledge_chunks_scope_per_version", "brand_dna_version_id", "scope"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id"))
    brand_dna_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brand_dna_versions.id")
    )
    section: Mapped[str] = mapped_column(Text())
    rule_type: Mapped[str] = mapped_column(Text())
    scope: Mapped[KnowledgeScope] = mapped_column(Enum(KnowledgeScope, name="knowledge_scope"))
    mandatory: Mapped[bool] = mapped_column(Boolean())
    content: Mapped[str] = mapped_column(Text())
    # `metadata` is reserved by SQLAlchemy's Declarative API: the Python attribute
    # is `chunk_metadata`, mapped explicitly to the canonical DB column name.
    chunk_metadata: Mapped[dict] = mapped_column("metadata", JSON())
    embedding: Mapped[list[float]] = mapped_column(Embedding())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
