"""ORM model for content review decisions (DATA_MODEL.md).

`creative_items.workflow_status` and `workflow_events` belong to
`app.creative.models` (Creative Studio created them); this module only owns
`content_reviews` and the transitions that write to those shared tables.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ContentReviewDecision(enum.StrEnum):
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


class ContentReview(Base):
    """Immutable decision on a frozen submitted version; never updated, only inserted."""

    __tablename__ = "content_reviews"
    __table_args__ = (
        UniqueConstraint(
            "creative_item_id",
            "submitted_version_id",
            "decision",
            name="uq_content_reviews_item_version_decision",
        ),
        Index("ix_content_reviews_creative_item_id", "creative_item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    creative_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("creative_items.id"))
    submitted_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("creative_versions.id"))
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    decision: Mapped[ContentReviewDecision] = mapped_column(
        Enum(ContentReviewDecision, name="content_review_decision")
    )
    feedback: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
