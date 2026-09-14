"""Schemas for the governance module: strict inputs and API resources (API.md).

Reuses Creative's resource shapes (`ItemOut`, `VersionOut`, `VersionSummary`,
`AppliedContextOut`) instead of redefining the frozen version/context shape:
governance decides on Creative's data, it does not own a parallel copy of it.
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.creative.schemas import AppliedContextOut, ItemSummary, VersionOut, VersionSummary
from app.governance.models import ContentReviewDecision

Feedback = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class RequestChangesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback: Feedback


class QueueItemOut(BaseModel):
    item: ItemSummary
    submitted_version: VersionSummary
    submitted_at: datetime


class QueueOut(BaseModel):
    items: list[QueueItemOut]


class ReviewOut(BaseModel):
    id: uuid.UUID
    creative_item_id: uuid.UUID
    submitted_version_id: uuid.UUID
    reviewer_id: uuid.UUID
    decision: ContentReviewDecision
    feedback: str | None
    created_at: datetime


class ReviewDetailOut(BaseModel):
    """`submitted_version`/`applied_context`/`latest_review` are null until the
    item's first submission (readable by the Creator before then, too)."""

    item: ItemSummary
    submitted_version: VersionOut | None
    applied_context: AppliedContextOut | None
    latest_review: ReviewOut | None


class WorkflowEventOut(BaseModel):
    id: uuid.UUID
    creative_item_id: uuid.UUID
    event_type: str
    actor_id: uuid.UUID | None
    metadata: dict
    created_at: datetime


class ReviewHistoryOut(BaseModel):
    events: list[WorkflowEventOut]


class DecisionOut(BaseModel):
    """Response for approve/request-changes: the item's new state + the decision."""

    item: ItemSummary
    review: ReviewOut
