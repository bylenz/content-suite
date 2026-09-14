"""ORM models for Creative items, versions and workflow events (DATA_MODEL.md)."""

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
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CreativeItemType(enum.StrEnum):
    PRODUCT_DESCRIPTION = "PRODUCT_DESCRIPTION"
    VIDEO_SCRIPT = "VIDEO_SCRIPT"
    IMAGE_PROMPT = "IMAGE_PROMPT"


class CreativeVersionOrigin(enum.StrEnum):
    AI_GENERATED = "AI_GENERATED"
    AI_REGENERATED = "AI_REGENERATED"
    HUMAN_EDIT = "HUMAN_EDIT"


class CreativeWorkflowStatus(enum.StrEnum):
    """Main workflow states (WORKFLOWS.md); phase 5 governance owns the review states."""

    DRAFT = "DRAFT"
    PENDING_CONTENT_REVIEW = "PENDING_CONTENT_REVIEW"
    CONTENT_CHANGES_REQUESTED = "CONTENT_CHANGES_REQUESTED"
    CONTENT_APPROVED = "CONTENT_APPROVED"
    PENDING_VISUAL_REVIEW = "PENDING_VISUAL_REVIEW"
    VISUAL_CHANGES_REQUESTED = "VISUAL_CHANGES_REQUESTED"
    FINAL_APPROVED = "FINAL_APPROVED"


class CreativeItem(Base):
    __tablename__ = "creative_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id"))
    type: Mapped[CreativeItemType] = mapped_column(
        Enum(CreativeItemType, name="creative_item_type")
    )
    title: Mapped[str] = mapped_column(String())
    workflow_status: Mapped[CreativeWorkflowStatus] = mapped_column(
        Enum(CreativeWorkflowStatus, name="creative_workflow_status")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CreativeVersion(Base):
    """Immutable content version; edits always insert a new row (never UPDATE).

    `applied_rule_ids` is stored as a JSON list of rule refs (the validated
    ai.contracts RuleRef strings) instead of a native uuid[] for portability
    across the SQLite test seam and PostgreSQL.
    """

    __tablename__ = "creative_versions"
    __table_args__ = (
        UniqueConstraint("creative_item_id", "version", name="uq_creative_versions_item_version"),
        Index("ix_creative_versions_creative_item_id", "creative_item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    creative_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("creative_items.id")
    )
    version: Mapped[int] = mapped_column(Integer)
    brand_dna_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("brand_dna_versions.id")
    )
    origin: Mapped[CreativeVersionOrigin] = mapped_column(
        Enum(CreativeVersionOrigin, name="creative_version_origin")
    )
    brief: Mapped[dict] = mapped_column(JSON())
    output: Mapped[dict | None] = mapped_column(JSON())
    applied_rule_ids: Mapped[list] = mapped_column(JSON())
    consistency_result: Mapped[dict | None] = mapped_column(JSON())
    consistency_score: Mapped[float | None] = mapped_column(Numeric())
    langfuse_trace_id: Mapped[str | None] = mapped_column(String())
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WorkflowEvent(Base):
    """Append-only workflow history (DATA_MODEL.md); `metadata` maps the column name."""

    __tablename__ = "workflow_events"
    __table_args__ = (Index("ix_workflow_events_creative_item_id", "creative_item_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    creative_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("creative_items.id"))
    event_type: Mapped[str] = mapped_column(String())
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("profiles.id"))
    event_metadata: Mapped[dict] = mapped_column("metadata", JSON())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
