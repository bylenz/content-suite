"""Repository for creative persistence. All SQL lives here."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.brand_dna import repository as brand_dna_repository
from app.brand_dna.models import BrandDnaVersion
from app.creative.models import CreativeItem, CreativeVersion, CreativeWorkflowStatus, WorkflowEvent
from app.identity import repository as identity_repository
from app.identity.models import BrandMembership

SUBMITTED_EVENT = "SUBMITTED"


def get_membership(
    session: Session, profile_id: uuid.UUID, brand_id: uuid.UUID
) -> BrandMembership | None:
    return identity_repository.get_membership(session, profile_id, brand_id)


def list_membership_brand_ids(session: Session, profile_id: uuid.UUID) -> list[uuid.UUID]:
    return [
        membership.brand_id
        for membership in identity_repository.list_memberships(session, profile_id)
    ]


def get_item(session: Session, item_id: uuid.UUID) -> CreativeItem | None:
    return session.get(CreativeItem, item_id)


def lock_item(session: Session, item_id: uuid.UUID) -> CreativeItem | None:
    """SELECT ... FOR UPDATE on the item row; serializes mutations per item on PostgreSQL."""
    return session.get(CreativeItem, item_id, with_for_update=True)


def list_items(session: Session, brand_ids: Sequence[uuid.UUID]) -> list[CreativeItem]:
    if not brand_ids:
        return []
    stmt = (
        select(CreativeItem)
        .where(CreativeItem.brand_id.in_(brand_ids))
        .order_by(CreativeItem.updated_at.desc(), CreativeItem.created_at.desc())
    )
    return list(session.scalars(stmt))


def count_by_workflow_status(
    session: Session, brand_id: uuid.UUID
) -> dict[CreativeWorkflowStatus, int]:
    """Item counts per real `workflow_status` value, zero-filled for absent states
    (change 014: pipeline breakdown must expose all 7 states, never omit one)."""
    counts: dict[CreativeWorkflowStatus, int] = {status: 0 for status in CreativeWorkflowStatus}
    stmt = (
        select(CreativeItem.workflow_status, func.count())
        .where(CreativeItem.brand_id == brand_id)
        .group_by(CreativeItem.workflow_status)
    )
    for workflow_status, count in session.execute(stmt):
        counts[workflow_status] = count
    return counts


def get_active_brand_dna_version(session: Session, brand_id: uuid.UUID) -> BrandDnaVersion | None:
    return brand_dna_repository.get_active(session, brand_id)


def get_active_brand_dna_version_id(session: Session, brand_id: uuid.UUID) -> uuid.UUID | None:
    active = brand_dna_repository.get_active(session, brand_id)
    return active.id if active is not None else None


def get_versions(session: Session, item_id: uuid.UUID) -> list[CreativeVersion]:
    stmt = (
        select(CreativeVersion)
        .where(CreativeVersion.creative_item_id == item_id)
        .order_by(CreativeVersion.version.desc())
    )
    return list(session.scalars(stmt))


def get_version_by_id(
    session: Session, item_id: uuid.UUID, version_id: uuid.UUID
) -> CreativeVersion | None:
    stmt = select(CreativeVersion).where(
        CreativeVersion.creative_item_id == item_id, CreativeVersion.id == version_id
    )
    return session.scalars(stmt).first()


def latest_version(session: Session, item_id: uuid.UUID) -> CreativeVersion | None:
    stmt = (
        select(CreativeVersion)
        .where(CreativeVersion.creative_item_id == item_id)
        .order_by(CreativeVersion.version.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def max_version(session: Session, item_id: uuid.UUID) -> int:
    latest = latest_version(session, item_id)
    return latest.version if latest is not None else 0


def record_consistency_result(
    session: Session,
    version_id: uuid.UUID,
    *,
    consistency_result: dict,
    consistency_score: float,
) -> None:
    """Persist a consistency check outcome on the audited version.

    Targeted UPDATE of the audit projection columns ONLY: content fields
    (brief/output/applied_rule_ids/brand_dna_version_id) stay immutable by
    construction — there is no code path that writes them after insert.
    """
    session.execute(
        update(CreativeVersion)
        .where(CreativeVersion.id == version_id)
        .values(
            consistency_result=consistency_result,
            consistency_score=consistency_score,
        )
    )


def add_workflow_event(
    session: Session,
    item_id: uuid.UUID,
    event_type: str,
    actor_id: uuid.UUID | None,
    metadata: dict,
) -> WorkflowEvent:
    event = WorkflowEvent(
        id=uuid.uuid4(),
        creative_item_id=item_id,
        event_type=event_type,
        actor_id=actor_id,
        event_metadata=metadata,
    )
    session.add(event)
    return event


def list_workflow_events(session: Session, item_id: uuid.UUID) -> list[WorkflowEvent]:
    stmt = (
        select(WorkflowEvent)
        .where(WorkflowEvent.creative_item_id == item_id)
        .order_by(WorkflowEvent.created_at.desc(), WorkflowEvent.id.desc())
    )
    return list(session.scalars(stmt))


def last_submitted_version_id(session: Session, item_id: uuid.UUID) -> uuid.UUID | None:
    """Version id behind the most recent SUBMITTED event (idempotency anchor)."""
    stmt = (
        select(WorkflowEvent.event_metadata)
        .where(
            WorkflowEvent.creative_item_id == item_id,
            WorkflowEvent.event_type == SUBMITTED_EVENT,
        )
        .order_by(WorkflowEvent.created_at.desc(), WorkflowEvent.id.desc())
        .limit(1)
    )
    metadata = session.scalar(stmt)
    if not metadata:
        return None
    raw = metadata.get("version_id")
    try:
        return uuid.UUID(str(raw)) if raw else None
    except ValueError:
        return None


def submitted_version_ids(session: Session, item_id: uuid.UUID) -> set[uuid.UUID]:
    """Every version id that has ever been submitted (JSON list extraction via SQL)."""
    stmt = select(WorkflowEvent.event_metadata).where(
        WorkflowEvent.creative_item_id == item_id,
        WorkflowEvent.event_type == SUBMITTED_EVENT,
    )
    ids: set[uuid.UUID] = set()
    for metadata in session.scalars(stmt):
        raw = metadata.get("version_id")
        if not raw:
            continue
        try:
            ids.add(uuid.UUID(str(raw)))
        except ValueError:
            continue
    return ids
