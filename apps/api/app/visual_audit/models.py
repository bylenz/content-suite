"""ORM models for visual assets, audits and reviews (DATA_MODEL.md).

Mirrors the creative/governance shape: `VisualAsset` and `VisualAudit` are
insert-only (no UPDATE path exists in the repository); `VisualReview` is
insert-only too (design D7 -- decisions are immutable). `creative_items` and
`workflow_events` belong to `app.creative.models`; this module only owns its
own three tables.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class VisualReviewDecision(enum.StrEnum):
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


class VisualAsset(Base):
    """Immutable visual version linked to a creative item; edits always insert
    a new version row (never UPDATE) -- an audited version never mutates."""

    __tablename__ = "visual_assets"
    __table_args__ = (
        UniqueConstraint("creative_item_id", "version", name="uq_visual_assets_item_version"),
        Index("ix_visual_assets_creative_item_id", "creative_item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    creative_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("creative_items.id"))
    version: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(Text())
    asset_metadata: Mapped[dict] = mapped_column("metadata", JSON())
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class VisualAudit(Base):
    """Insert-only auditory record: re-running an audit creates a new row,
    never mutates a previous one (design D6)."""

    __tablename__ = "visual_audits"
    __table_args__ = (Index("ix_visual_audits_visual_asset_id", "visual_asset_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    visual_asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("visual_assets.id"))
    brand_dna_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brand_dna_versions.id"))
    checks: Mapped[list] = mapped_column(JSON())
    findings: Mapped[list] = mapped_column(JSON())
    score: Mapped[float] = mapped_column(Numeric())
    summary: Mapped[str] = mapped_column(Text())
    # Sanitized snapshot of the applied context (rule count/scope), never the
    # raw prompt or provider response.
    applied_context: Mapped[dict] = mapped_column(JSON())
    langfuse_trace_id: Mapped[str | None] = mapped_column(String())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class VisualReview(Base):
    """Immutable reviewer decision on an exact audit; never updated, only inserted."""

    __tablename__ = "visual_reviews"
    __table_args__ = (
        UniqueConstraint(
            "visual_audit_id",
            "reviewer_id",
            "decision",
            name="uq_visual_reviews_audit_reviewer_decision",
        ),
        Index("ix_visual_reviews_visual_audit_id", "visual_audit_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    visual_audit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("visual_audits.id"))
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    decision: Mapped[VisualReviewDecision] = mapped_column(
        Enum(VisualReviewDecision, name="visual_review_decision")
    )
    feedback: Mapped[str | None] = mapped_column(Text())
    exception_accepted: Mapped[bool] = mapped_column(Boolean(), default=False)
    # HIGH-fail finding evidence persisted with the decision (design D7); null
    # when the approval had no HIGH findings to except.
    evidence: Mapped[dict | None] = mapped_column(JSON())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
