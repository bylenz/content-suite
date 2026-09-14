"""Repository for governance persistence. All SQL lives here.

Reuses `app.creative.repository` for the tables Creative Studio already owns
(`creative_items`, `creative_versions`, `workflow_events`) instead of
duplicating access to them; this module's own table is `content_reviews`.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.creative import repository as creative_repository
from app.creative.models import CreativeItem, CreativeWorkflowStatus, WorkflowEvent
from app.governance.models import ContentReview, ContentReviewDecision

# Re-exported so the service module has one import surface for the shared tables.
get_membership = creative_repository.get_membership
list_membership_brand_ids = creative_repository.list_membership_brand_ids
get_item = creative_repository.get_item
lock_item = creative_repository.lock_item
get_version_by_id = creative_repository.get_version_by_id
latest_version = creative_repository.latest_version
last_submitted_version_id = creative_repository.last_submitted_version_id
add_workflow_event = creative_repository.add_workflow_event
list_workflow_events = creative_repository.list_workflow_events

APPROVED_EVENT = "CONTENT_APPROVED"
CHANGES_REQUESTED_EVENT = "CONTENT_CHANGES_REQUESTED"


def queue(session: Session, brand_ids: Sequence[uuid.UUID]) -> list[CreativeItem]:
    """Items PENDING_CONTENT_REVIEW across the reviewer's brands, oldest submit first."""
    if not brand_ids:
        return []
    latest_submit = (
        select(
            WorkflowEvent.creative_item_id.label("creative_item_id"),
            func.max(WorkflowEvent.created_at).label("submitted_at"),
        )
        .where(WorkflowEvent.event_type == creative_repository.SUBMITTED_EVENT)
        .group_by(WorkflowEvent.creative_item_id)
        .subquery()
    )
    stmt = (
        select(CreativeItem)
        .join(latest_submit, latest_submit.c.creative_item_id == CreativeItem.id)
        .where(
            CreativeItem.brand_id.in_(brand_ids),
            CreativeItem.workflow_status == CreativeWorkflowStatus.PENDING_CONTENT_REVIEW,
        )
        .order_by(latest_submit.c.submitted_at.asc(), CreativeItem.id.asc())
    )
    return list(session.scalars(stmt))


def insert_review(
    session: Session,
    *,
    item_id: uuid.UUID,
    submitted_version_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    decision: ContentReviewDecision,
    feedback: str | None,
) -> ContentReview:
    review = ContentReview(
        id=uuid.uuid4(),
        creative_item_id=item_id,
        submitted_version_id=submitted_version_id,
        reviewer_id=reviewer_id,
        decision=decision,
        feedback=feedback,
    )
    session.add(review)
    return review


def get_review(
    session: Session,
    item_id: uuid.UUID,
    submitted_version_id: uuid.UUID,
    decision: ContentReviewDecision,
) -> ContentReview | None:
    """Idempotency read-back: the decision already persisted for this exact version, if any."""
    stmt = select(ContentReview).where(
        ContentReview.creative_item_id == item_id,
        ContentReview.submitted_version_id == submitted_version_id,
        ContentReview.decision == decision,
    )
    return session.scalars(stmt).first()


def latest_review(session: Session, item_id: uuid.UUID) -> ContentReview | None:
    """Most recent decision on an item, regardless of version (for status/feedback display)."""
    stmt = (
        select(ContentReview)
        .where(ContentReview.creative_item_id == item_id)
        .order_by(ContentReview.created_at.desc(), ContentReview.id.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()
