"""Application service for brand_dna: role-filtered reads, locked draft upsert,
transactional publish, and Knowledge status transitions (without sync)."""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.brand_dna import policies, repository
from app.brand_dna.models import BrandDnaStatus, BrandDnaVersion, KnowledgeStatus
from app.brand_dna.schemas import (
    BrandDnaDocument,
    BrandDnaVersionOut,
    BrandDnaVersionSummary,
    derive_section_counts,
)
from app.identity.auth import AuthenticatedUser
from app.identity.models import BrandRole


def _flush(session: Session) -> None:
    """Flush indirection so tests can inject IntegrityError races deterministically."""
    session.flush()


def _to_out(version: BrandDnaVersion) -> BrandDnaVersionOut:
    document = BrandDnaDocument.model_validate(version.document)
    return BrandDnaVersionOut(
        id=version.id,
        brand_id=version.brand_id,
        version=version.version,
        status=version.status,
        document=document,
        created_by=version.created_by,
        created_at=version.created_at,
        published_at=version.published_at,
        knowledge_status=version.knowledge_status,
        section_counts=derive_section_counts(document),
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand DNA not found")


def _resolve_reader_membership(session: Session, user: AuthenticatedUser, brand_id: uuid.UUID):
    membership = repository.get_membership(session, user.id, brand_id)
    # Without membership the 403 is answered before evaluating any resource (design matrix).
    policies.require_reader(membership)
    return membership


def get_brand_dna(
    session: Session, user: AuthenticatedUser, brand_id: uuid.UUID
) -> dict[str, BrandDnaVersionOut | None]:
    membership = _resolve_reader_membership(session, user, brand_id)
    active = repository.get_active(session, brand_id)
    # Drafts are visible only to CREATOR; reviewers always receive null.
    draft = (
        repository.get_draft(session, brand_id) if membership.role == BrandRole.CREATOR else None
    )
    return {
        "active": _to_out(active) if active else None,
        "draft": _to_out(draft) if draft else None,
    }


def list_versions(
    session: Session, user: AuthenticatedUser, brand_id: uuid.UUID
) -> list[BrandDnaVersionSummary]:
    membership = _resolve_reader_membership(session, user, brand_id)
    include_draft = membership.role == BrandRole.CREATOR
    versions = repository.list_versions(session, brand_id, include_draft=include_draft)
    return [
        BrandDnaVersionSummary(
            id=v.id,
            brand_id=v.brand_id,
            version=v.version,
            status=v.status,
            created_by=v.created_by,
            created_at=v.created_at,
            published_at=v.published_at,
            knowledge_status=v.knowledge_status,
            section_counts=derive_section_counts(BrandDnaDocument.model_validate(v.document)),
        )
        for v in versions
    ]


def get_version(
    session: Session, user: AuthenticatedUser, brand_id: uuid.UUID, version: int
) -> BrandDnaVersionOut:
    membership = _resolve_reader_membership(session, user, brand_id)
    found = repository.get_version(session, brand_id, version)
    if found is None:
        raise _not_found()
    if found.status == BrandDnaStatus.DRAFT and membership.role != BrandRole.CREATOR:
        # A reviewer's 404 must not confirm the draft's existence.
        raise _not_found()
    return _to_out(found)


def _apply_draft_upsert(
    session: Session,
    actor_id: uuid.UUID,
    brand_id: uuid.UUID,
    document: BrandDnaDocument,
) -> BrandDnaVersion:
    """Upsert the single DRAFT under the brand row lock. Caller owns the transaction."""
    if repository.lock_brand(session, brand_id) is None:
        raise _not_found()
    draft = repository.get_draft(session, brand_id)
    if draft is None:
        # Next version, initialized from the ACTIVE document's lineage; PATCH is a full
        # replacement, so the stored document is the request's document. ACTIVE/ARCHIVED
        # versions are never modified.
        draft = BrandDnaVersion(
            id=uuid.uuid4(),
            brand_id=brand_id,
            version=repository.max_version(session, brand_id) + 1,
            status=BrandDnaStatus.DRAFT,
            document=document.model_dump(mode="json"),
            created_by=actor_id,
            knowledge_status=KnowledgeStatus.NOT_SYNCED,
        )
        session.add(draft)
    else:
        draft.document = document.model_dump(mode="json")
    _mark_active_outdated(session, brand_id)
    _flush(session)
    return draft


def _mark_active_outdated(session: Session, brand_id: uuid.UUID) -> None:
    """SYNCED -> OUTDATED on the current ACTIVE; other states are left untouched (idempotent)."""
    active = repository.get_active(session, brand_id)
    if active is not None and active.knowledge_status == KnowledgeStatus.SYNCED:
        active.knowledge_status = KnowledgeStatus.OUTDATED


def upsert_draft(
    session: Session, user: AuthenticatedUser, brand_id: uuid.UUID, document: BrandDnaDocument
) -> BrandDnaVersionOut:
    membership = repository.get_membership(session, user.id, brand_id)
    policies.require_writer(membership)
    try:
        draft = _apply_draft_upsert(session, user.id, brand_id, document)
        session.commit()
    except IntegrityError:
        # Race escaped the lock (partial/unique index): deterministic recovery —
        # rollback, re-read under lock and re-apply the upsert; never a 5xx.
        session.rollback()
        draft = _apply_draft_upsert(session, user.id, brand_id, document)
        session.commit()
    return _to_out(draft)


def _publish_locked(
    session: Session, brand_id: uuid.UUID, expected_draft_id: uuid.UUID
) -> BrandDnaVersion:
    """Publish under the brand row lock. Mandatory sequence per design.md:
    lock -> load draft+active -> ACTIVE -> ARCHIVED + flush -> DRAFT -> ACTIVE
    (+ published_at + NOT_SYNCED) -> flush. Caller commits."""
    if repository.lock_brand(session, brand_id) is None:
        raise _not_found()
    draft = repository.get_draft(session, brand_id)
    active = repository.get_active(session, brand_id)
    if draft is None:
        if active is None:
            raise policies.InvalidWorkflowTransitionError(
                "No draft or version exists to publish",
                {"expected_draft_id": expected_draft_id, "active_version_id": None},
            )
        if active.id == expected_draft_id:
            return active  # idempotent retry: already published
        raise policies.InvalidWorkflowTransitionError(
            "expected_draft_id does not match the current active version",
            {"expected_draft_id": expected_draft_id, "active_version_id": active.id},
        )
    if draft.id != expected_draft_id:
        raise policies.InvalidWorkflowTransitionError(
            "expected_draft_id does not match the current draft",
            {
                "expected_draft_id": expected_draft_id,
                "active_version_id": active.id if active else None,
            },
        )
    if active is not None:
        active.status = BrandDnaStatus.ARCHIVED
        # Flush frees the partial ACTIVE unique index before the new ACTIVE is written.
        _flush(session)
    draft.status = BrandDnaStatus.ACTIVE
    draft.published_at = datetime.now(UTC)
    draft.knowledge_status = KnowledgeStatus.NOT_SYNCED
    _flush(session)
    return draft


def publish(
    session: Session, user: AuthenticatedUser, brand_id: uuid.UUID, expected_draft_id: uuid.UUID
) -> BrandDnaVersionOut:
    membership = repository.get_membership(session, user.id, brand_id)
    policies.require_writer(membership)
    try:
        published = _publish_locked(session, brand_id, expected_draft_id)
        session.commit()
    except policies.InvalidWorkflowTransitionError:
        session.rollback()
        raise
    except IntegrityError:
        # Race escaped the lock (partial ACTIVE index): deterministic recovery —
        # rollback, re-read under lock and apply the same mapping (match -> idempotent
        # retry; mismatch -> 409); never a 5xx.
        session.rollback()
        repository.lock_brand(session, brand_id)
        draft = repository.get_draft(session, brand_id)
        active = repository.get_active(session, brand_id)
        if draft is not None and draft.id == expected_draft_id:
            published = _publish_locked(session, brand_id, expected_draft_id)
            session.commit()
        elif draft is None and active is not None and active.id == expected_draft_id:
            published = active  # concurrent request published our draft: idempotent
        else:
            raise policies.InvalidWorkflowTransitionError(
                "Publish conflicted with a concurrent publication",
                {
                    "expected_draft_id": expected_draft_id,
                    "active_version_id": active.id if active else None,
                },
            ) from None
    return _to_out(published)
