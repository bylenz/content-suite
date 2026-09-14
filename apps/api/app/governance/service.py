"""Application service for governance: review queue, detail, approve, request-changes.

Transactional commands follow the creative/brand_dna precedent: lock the item
row (`SELECT ... FOR UPDATE`), decide in Python, commit once. No `await`
happens between lock and commit — there is no provider/I/O call in this
module at all (design.md: decisions never invoke AI).

Guard order note: `design.md` asks for membership-403 before resolving the
resource, but these endpoints are keyed only by `item_id` (no `brand_id` in
the path) — the item must be read to learn its brand before membership can
even be checked. Resolving that the same way `app.creative.service` already
does (404 for both a missing item and a non-member) still satisfies the
stated goal of "no existence leak by role/membership": the two cases stay
indistinguishable to the caller.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.contracts import CreativeOutput
from app.creative.models import CreativeItem, CreativeWorkflowStatus
from app.creative.schemas import AppliedContextOut, ItemSummary, VersionOut, VersionSummary
from app.governance import policies, repository
from app.governance.models import ContentReviewDecision
from app.governance.policies import InvalidWorkflowTransitionError
from app.governance.schemas import (
    DecisionOut,
    QueueItemOut,
    QueueOut,
    ReviewDetailOut,
    ReviewHistoryOut,
    ReviewOut,
    WorkflowEventOut,
)
from app.identity.auth import AuthenticatedUser


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creative item not found")


def _to_item_summary(session: Session, item: CreativeItem) -> ItemSummary:
    latest = repository.latest_version(session, item.id)
    return ItemSummary(
        id=item.id,
        brand_id=item.brand_id,
        type=item.type,
        title=item.title,
        workflow_status=item.workflow_status,
        created_by=item.created_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
        latest_version=latest.version if latest is not None else 0,
    )


def _to_review_out(review) -> ReviewOut:
    return ReviewOut(
        id=review.id,
        creative_item_id=review.creative_item_id,
        submitted_version_id=review.submitted_version_id,
        reviewer_id=review.reviewer_id,
        decision=review.decision,
        feedback=review.feedback,
        created_at=review.created_at,
    )


def _resolve_reader_item(
    session: Session, user: AuthenticatedUser, item_id: uuid.UUID
) -> CreativeItem:
    """404 for both a missing item and a non-member (no existence leak)."""
    item = repository.get_item(session, item_id)
    if item is None:
        raise _not_found()
    membership = repository.get_membership(session, user.id, item.brand_id)
    if membership is None:
        raise _not_found()
    policies.require_reader(membership)
    return item


def _submitted_version(session: Session, item: CreativeItem):
    """The frozen version behind the item's most recent SUBMITTED event, or None
    if the item has never been submitted."""
    version_id = repository.last_submitted_version_id(session, item.id)
    if version_id is None:
        return None
    return repository.get_version_by_id(session, item.id, version_id)


def _require_submitted_version(session: Session, item: CreativeItem):
    """Same as `_submitted_version`, but the caller only reaches this state when a
    submission is guaranteed to exist (e.g. `workflow_status == PENDING_CONTENT_REVIEW`);
    a `None` here means the data is inconsistent, not that the caller made a bad request."""
    version = _submitted_version(session, item)
    if version is None:
        raise _not_found()
    return version


def queue(session: Session, user: AuthenticatedUser) -> QueueOut:
    brand_ids = repository.list_membership_brand_ids(session, user.id)
    items = []
    for item in repository.queue(session, brand_ids):
        membership = repository.get_membership(session, user.id, item.brand_id)
        policies.require_reviewer(membership)
        # Every queued item is PENDING_CONTENT_REVIEW, which only happens after submit.
        version = _require_submitted_version(session, item)
        items.append(
            QueueItemOut(
                item=_to_item_summary(session, item),
                submitted_version=VersionSummary(
                    id=version.id,
                    creative_item_id=version.creative_item_id,
                    version=version.version,
                    origin=version.origin,
                    brand_dna_version_id=version.brand_dna_version_id,
                    consistency_score=(
                        float(version.consistency_score)
                        if version.consistency_score is not None
                        else None
                    ),
                    created_by=version.created_by,
                    created_at=version.created_at,
                ),
                submitted_at=version.created_at,
            )
        )
    return QueueOut(items=items)


def detail(session: Session, user: AuthenticatedUser, item_id: uuid.UUID) -> ReviewDetailOut:
    """The frozen submitted version + context + latest decision, if any exists yet.

    Readable by the Creator before any submission too (Creative Studio's status
    block), in which case `submitted_version`/`applied_context`/`latest_review`
    are all null rather than 404 — the item itself is a perfectly valid resource.
    """
    item = _resolve_reader_item(session, user, item_id)
    version = _submitted_version(session, item)
    review = repository.latest_review(session, item.id) if version is not None else None
    return ReviewDetailOut(
        item=_to_item_summary(session, item),
        submitted_version=_to_version_out(version) if version is not None else None,
        applied_context=(
            AppliedContextOut(
                creative_item_id=item.id,
                version_id=version.id,
                version=version.version,
                brand_dna_version_id=version.brand_dna_version_id,
                applied_rule_ids=version.applied_rule_ids or [],
            )
            if version is not None
            else None
        ),
        latest_review=_to_review_out(review) if review is not None else None,
    )


def _to_version_out(version) -> VersionOut:
    return VersionOut(
        id=version.id,
        creative_item_id=version.creative_item_id,
        version=version.version,
        origin=version.origin,
        brand_dna_version_id=version.brand_dna_version_id,
        consistency_score=(
            float(version.consistency_score) if version.consistency_score is not None else None
        ),
        created_by=version.created_by,
        created_at=version.created_at,
        brief=version.brief,
        output=(CreativeOutput.model_validate(version.output) if version.output is not None else None),
        applied_rule_ids=version.applied_rule_ids or [],
        consistency_result=version.consistency_result,
        langfuse_trace_id=version.langfuse_trace_id,
    )


def history(session: Session, user: AuthenticatedUser, item_id: uuid.UUID) -> ReviewHistoryOut:
    item = _resolve_reader_item(session, user, item_id)
    events = repository.list_workflow_events(session, item.id)
    ordered = sorted(events, key=lambda e: (e.created_at, e.id))
    return ReviewHistoryOut(
        events=[
            WorkflowEventOut(
                id=e.id,
                creative_item_id=e.creative_item_id,
                event_type=e.event_type,
                actor_id=e.actor_id,
                metadata=e.event_metadata,
                created_at=e.created_at,
            )
            for e in ordered
        ]
    )


def approve(session: Session, user: AuthenticatedUser, item_id: uuid.UUID) -> DecisionOut:
    return _decide(
        session,
        user,
        item_id,
        decision=ContentReviewDecision.APPROVED,
        dest_status=CreativeWorkflowStatus.CONTENT_APPROVED,
        event_type=repository.APPROVED_EVENT,
        feedback=None,
    )


def request_changes(
    session: Session, user: AuthenticatedUser, item_id: uuid.UUID, feedback: str
) -> DecisionOut:
    return _decide(
        session,
        user,
        item_id,
        decision=ContentReviewDecision.CHANGES_REQUESTED,
        dest_status=CreativeWorkflowStatus.CONTENT_CHANGES_REQUESTED,
        event_type=repository.CHANGES_REQUESTED_EVENT,
        feedback=feedback,
    )


def _decide(
    session: Session,
    user: AuthenticatedUser,
    item_id: uuid.UUID,
    *,
    decision: ContentReviewDecision,
    dest_status: CreativeWorkflowStatus,
    event_type: str,
    feedback: str | None,
) -> DecisionOut:
    item = repository.get_item(session, item_id)
    if item is None:
        raise _not_found()
    membership = repository.get_membership(session, user.id, item.brand_id)
    if membership is None:
        raise _not_found()
    policies.require_reviewer(membership)

    try:
        result = _decide_locked(
            session,
            user,
            item_id,
            decision=decision,
            dest_status=dest_status,
            event_type=event_type,
            feedback=feedback,
        )
        session.commit()
    except InvalidWorkflowTransitionError:
        session.rollback()
        raise
    except IntegrityError:
        # SQLite's SELECT-FOR-UPDATE is a no-op (no row-level locking, unlike
        # Postgres), so two concurrent decisions can both read
        # PENDING_CONTENT_REVIEW before either commits; the loser's INSERT
        # then trips the (item, version, decision) UNIQUE constraint instead
        # of being serialized by the lock. Same recovery as
        # `app.creative.service.submit`: rollback and re-run once — the retry
        # now sees the winner's committed state and takes the idempotent path.
        session.rollback()
        result = _decide_locked(
            session,
            user,
            item_id,
            decision=decision,
            dest_status=dest_status,
            event_type=event_type,
            feedback=feedback,
        )
        session.commit()
    return result


def _decide_locked(
    session: Session,
    user: AuthenticatedUser,
    item_id: uuid.UUID,
    *,
    decision: ContentReviewDecision,
    dest_status: CreativeWorkflowStatus,
    event_type: str,
    feedback: str | None,
) -> DecisionOut:
    """Lock the item and either transition it or read back an idempotent decision.

    No `session.commit()`/`rollback()` here: the caller commits once on
    success (including the idempotent-return path, which writes nothing but
    still needs to release the `FOR UPDATE` lock) and rolls back once on the
    409 path, matching `app.creative.service.submit`'s split.
    """
    locked = repository.lock_item(session, item_id)
    if locked is None:
        raise _not_found()

    if locked.workflow_status != CreativeWorkflowStatus.PENDING_CONTENT_REVIEW:
        # Not decidable right now (never submitted, still in review, or already
        # decided): the only way this is still a 200 is an idempotent retry of
        # the exact same decision on the version it was made against.
        stale = _submitted_version(session, locked)
        existing = (
            repository.get_review(session, locked.id, stale.id, decision)
            if stale is not None
            else None
        )
        if existing is not None:
            return DecisionOut(
                item=_to_item_summary(session, locked), review=_to_review_out(existing)
            )
        raise InvalidWorkflowTransitionError(
            "Creative item is not pending content review",
            {"item_id": locked.id, "workflow_status": locked.workflow_status.value},
        )

    # PENDING_CONTENT_REVIEW is only reachable via submit, which always leaves a
    # frozen version behind — safe to require it here.
    version = _require_submitted_version(session, locked)
    locked.workflow_status = dest_status
    review = repository.insert_review(
        session,
        item_id=locked.id,
        submitted_version_id=version.id,
        reviewer_id=user.id,
        decision=decision,
        feedback=feedback,
    )
    repository.add_workflow_event(
        session,
        locked.id,
        event_type,
        user.id,
        {"version_id": str(version.id), "version": version.version, "review_id": str(review.id)},
    )
    session.flush()
    return DecisionOut(item=_to_item_summary(session, locked), review=_to_review_out(review))
