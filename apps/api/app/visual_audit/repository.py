"""Repository for visual_audit persistence. All SQL lives here.

Reuses `app.creative.repository` for the tables Creative Studio already owns
(`creative_items`, `workflow_events`) instead of duplicating access to them;
this module's own tables are `visual_assets`, `visual_audits`, `visual_reviews`.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.creative import repository as creative_repository
from app.creative.models import CreativeItem, CreativeWorkflowStatus
from app.visual_audit.models import VisualAsset, VisualAudit, VisualReview, VisualReviewDecision

# Re-exported so the service module has one import surface for the shared tables.
get_membership = creative_repository.get_membership
list_membership_brand_ids = creative_repository.list_membership_brand_ids
get_item = creative_repository.get_item
lock_item = creative_repository.lock_item
add_workflow_event = creative_repository.add_workflow_event
list_workflow_events = creative_repository.list_workflow_events

UPLOADED_EVENT = "VISUAL_UPLOADED"
APPROVED_EVENT = "FINAL_APPROVED"
CHANGES_REQUESTED_EVENT = "VISUAL_CHANGES_REQUESTED"


def latest_asset(session: Session, item_id: uuid.UUID) -> VisualAsset | None:
    stmt = (
        select(VisualAsset)
        .where(VisualAsset.creative_item_id == item_id)
        .order_by(VisualAsset.version.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def max_asset_version(session: Session, item_id: uuid.UUID) -> int:
    latest = latest_asset(session, item_id)
    return latest.version if latest is not None else 0


def list_assets(session: Session, item_id: uuid.UUID) -> list[VisualAsset]:
    stmt = (
        select(VisualAsset)
        .where(VisualAsset.creative_item_id == item_id)
        .order_by(VisualAsset.version.desc())
    )
    return list(session.scalars(stmt))


def get_asset(session: Session, asset_id: uuid.UUID) -> VisualAsset | None:
    return session.get(VisualAsset, asset_id)


def insert_asset(
    session: Session,
    *,
    creative_item_id: uuid.UUID,
    version: int,
    storage_path: str,
    metadata: dict,
    uploaded_by: uuid.UUID,
) -> VisualAsset:
    asset = VisualAsset(
        id=uuid.uuid4(),
        creative_item_id=creative_item_id,
        version=version,
        storage_path=storage_path,
        asset_metadata=metadata,
        uploaded_by=uploaded_by,
    )
    session.add(asset)
    return asset


def latest_audit(session: Session, visual_asset_id: uuid.UUID) -> VisualAudit | None:
    stmt = (
        select(VisualAudit)
        .where(VisualAudit.visual_asset_id == visual_asset_id)
        .order_by(VisualAudit.created_at.desc(), VisualAudit.id.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def list_audits(session: Session, visual_asset_id: uuid.UUID) -> list[VisualAudit]:
    stmt = (
        select(VisualAudit)
        .where(VisualAudit.visual_asset_id == visual_asset_id)
        .order_by(VisualAudit.created_at.desc(), VisualAudit.id.desc())
    )
    return list(session.scalars(stmt))


def get_audit(session: Session, audit_id: uuid.UUID) -> VisualAudit | None:
    return session.get(VisualAudit, audit_id)


def insert_audit(
    session: Session,
    *,
    visual_asset_id: uuid.UUID,
    brand_dna_version_id: uuid.UUID,
    checks: list,
    findings: list,
    score: float,
    summary: str,
    applied_context: dict,
    langfuse_trace_id: str | None,
) -> VisualAudit:
    audit = VisualAudit(
        id=uuid.uuid4(),
        visual_asset_id=visual_asset_id,
        brand_dna_version_id=brand_dna_version_id,
        checks=checks,
        findings=findings,
        score=score,
        summary=summary,
        applied_context=applied_context,
        langfuse_trace_id=langfuse_trace_id,
    )
    session.add(audit)
    return audit


def list_reviews(session: Session, visual_audit_id: uuid.UUID) -> list[VisualReview]:
    stmt = (
        select(VisualReview)
        .where(VisualReview.visual_audit_id == visual_audit_id)
        .order_by(VisualReview.created_at.desc(), VisualReview.id.desc())
    )
    return list(session.scalars(stmt))


def get_review(
    session: Session,
    visual_audit_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    decision: VisualReviewDecision,
) -> VisualReview | None:
    """Idempotency read-back: the decision already persisted for this exact
    reviewer+audit+decision, if any (design D7)."""
    stmt = select(VisualReview).where(
        VisualReview.visual_audit_id == visual_audit_id,
        VisualReview.reviewer_id == reviewer_id,
        VisualReview.decision == decision,
    )
    return session.scalars(stmt).first()


def insert_review(
    session: Session,
    *,
    visual_audit_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    decision: VisualReviewDecision,
    feedback: str | None,
    exception_accepted: bool,
    evidence: dict | None,
) -> VisualReview:
    review = VisualReview(
        id=uuid.uuid4(),
        visual_audit_id=visual_audit_id,
        reviewer_id=reviewer_id,
        decision=decision,
        feedback=feedback,
        exception_accepted=exception_accepted,
        evidence=evidence,
    )
    session.add(review)
    return review


def queue(session: Session, brand_ids: Sequence[uuid.UUID]) -> list[CreativeItem]:
    """Items PENDING_VISUAL_REVIEW across the reviewer's brands, oldest upload first."""
    if not brand_ids:
        return []
    # Portable "latest upload per item" (SQLite has no DISTINCT ON): rank in
    # Python after fetching CreativeItem rows in the target workflow state,
    # then order by each item's own latest asset creation time.
    stmt = select(CreativeItem).where(
        CreativeItem.brand_id.in_(brand_ids),
        CreativeItem.workflow_status == CreativeWorkflowStatus.PENDING_VISUAL_REVIEW,
    )
    items = list(session.scalars(stmt))
    keyed = []
    for item in items:
        asset = latest_asset(session, item.id)
        uploaded_at = asset.created_at if asset is not None else item.updated_at
        keyed.append((uploaded_at, item.id, item))
    keyed.sort(key=lambda row: (row[0], row[1]))
    return [item for _uploaded_at, _id, item in keyed]
