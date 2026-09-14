"""ORM models for Brand DNA versions, based on DATA_MODEL.md tables."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BrandDnaStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class KnowledgeStatus(enum.StrEnum):
    NOT_SYNCED = "NOT_SYNCED"
    SYNCING = "SYNCING"
    SYNCED = "SYNCED"
    OUTDATED = "OUTDATED"
    FAILED = "FAILED"


class BrandDnaVersion(Base):
    __tablename__ = "brand_dna_versions"
    __table_args__ = (
        # ponytail: partial unique indexes enforce one DRAFT/ACTIVE per brand at the DB level;
        # portable form (sqlite_where/postgresql_where) keeps SQLite tests and Supabase PG aligned.
        Index(
            "uq_brand_dna_versions_draft_per_brand",
            "brand_id",
            unique=True,
            sqlite_where=text("status = 'DRAFT'"),
            postgresql_where=text("status = 'DRAFT'"),
        ),
        Index(
            "uq_brand_dna_versions_active_per_brand",
            "brand_id",
            unique=True,
            sqlite_where=text("status = 'ACTIVE'"),
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id"))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[BrandDnaStatus] = mapped_column(Enum(BrandDnaStatus, name="brand_dna_status"))
    document: Mapped[dict] = mapped_column(JSON())
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    knowledge_status: Mapped[KnowledgeStatus] = mapped_column(
        Enum(KnowledgeStatus, name="brand_dna_knowledge_status")
    )
    # Sync evidence (change 006): written only on successful sync finalization, in the
    # same transaction as the chunks. Nullable by construction (additive migration).
    knowledge_embedding_model: Mapped[str | None] = mapped_column(String())
    knowledge_embedding_dimensions: Mapped[int | None] = mapped_column(Integer())
    knowledge_fingerprint: Mapped[str | None] = mapped_column(String())
