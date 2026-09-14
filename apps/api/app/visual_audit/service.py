"""Application service for visual_audit: upload, audit, decisions, queue and history.

Guard order note (mirrors `app.creative.service`/`app.governance.service`):
every command here is keyed by an existing resource id (`item_id`,
`asset_id`, `audit_id`), so the resource is resolved first, a missing
membership answers 404 (uniform with a missing resource -- no existence
leak), and only a member with the wrong role gets 403. There is no
brand_id-keyed creation endpoint in this module (unlike
`creative.service.create_item`), so the 403-before-lookup shape never
applies here.

Upload and audit follow the same provider-safety shape as knowledge
sync/creative generate: guards resolve first, storage/provider calls happen
with no open write transaction across them, and the insert is a short locked
transaction. Vision output validation failure never persists an audit
(design D6); a knowledge fail-safe never calls the model (design spec).
"""

import logging
import time
import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.contracts import Check, Finding, TraceSummary, VisualAuditResult
from app.ai.errors import AIOutputValidationError
from app.ai.ports import EmbeddingModel, VisionModel
from app.ai.runner import run_capability
from app.brand_assets import service as brand_assets_service
from app.config import Settings
from app.creative import repository as creative_repository
from app.creative.models import CreativeItem, CreativeWorkflowStatus
from app.creative.schemas import ItemSummary
from app.identity.auth import AuthenticatedUser
from app.knowledge import service as knowledge_service
from app.observability.ports import CapabilitySpan, Tracer
from app.storage import validation
from app.storage.errors import StorageNotConfiguredError
from app.storage.ports import StoragePort
from app.visual_audit import policies, repository
from app.visual_audit.errors import VisionOutputInvalidError
from app.visual_audit.models import VisualAsset, VisualAudit, VisualReview, VisualReviewDecision
from app.visual_audit.policies import InvalidWorkflowTransitionError
from app.visual_audit.schemas import (
    ApproveIn,
    DecisionOut,
    QueueItemOut,
    QueueOut,
    RequestChangesIn,
    VisualAssetList,
    VisualAssetOut,
    VisualAuditHistoryOut,
    VisualAuditOut,
    VisualHistoryEntryOut,
    VisualReviewOut,
)

logger = logging.getLogger(__name__)

AUDIT_PROMPT_ID = "audit.visual.v1"


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")


async def _emit(tracer: Tracer, span: CapabilitySpan) -> str | None:
    """Emit one span; tracer failures degrade to a sanitized warning, never propagate."""
    try:
        return await tracer.emit_span(span)
    except Exception as exc:
        logger.warning("Tracer failed while emitting span: %s", type(exc).__name__)
        return None


def _visual_path(brand_id: uuid.UUID, item_id: uuid.UUID, version: int, extension: str) -> str:
    return f"brands/{brand_id}/creative-items/{item_id}/visuals/v{version}{extension}"


def _to_item_summary(session: Session, item: CreativeItem) -> ItemSummary:
    latest = creative_repository.latest_version(session, item.id)
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


def _to_asset_out(asset: VisualAsset, signed_url: str) -> VisualAssetOut:
    return VisualAssetOut(
        id=asset.id,
        creative_item_id=asset.creative_item_id,
        version=asset.version,
        signed_url=signed_url,
        metadata=asset.asset_metadata,
        uploaded_by=asset.uploaded_by,
        created_at=asset.created_at,
    )


def _to_audit_out(audit: VisualAudit) -> VisualAuditOut:
    return VisualAuditOut(
        id=audit.id,
        visual_asset_id=audit.visual_asset_id,
        brand_dna_version_id=audit.brand_dna_version_id,
        checks=[Check.model_validate(c) for c in audit.checks],
        findings=[Finding.model_validate(f) for f in audit.findings],
        score=float(audit.score),
        summary=audit.summary,
        applied_context=audit.applied_context,
        langfuse_trace_id=audit.langfuse_trace_id,
        created_at=audit.created_at,
    )


def _to_review_out(review: VisualReview) -> VisualReviewOut:
    return VisualReviewOut(
        id=review.id,
        visual_audit_id=review.visual_audit_id,
        reviewer_id=review.reviewer_id,
        decision=review.decision,
        feedback=review.feedback,
        exception_accepted=review.exception_accepted,
        evidence=review.evidence,
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


def _resolve_item_for_upload(
    session: Session, user: AuthenticatedUser, item_id: uuid.UUID
) -> CreativeItem:
    item = repository.get_item(session, item_id)
    if item is None:
        raise _not_found()
    membership = repository.get_membership(session, user.id, item.brand_id)
    if membership is None:
        raise _not_found()
    policies.require_uploader(membership)
    policies.require_uploadable_state(item.workflow_status, item.id)
    return item


def _resolve_asset(
    session: Session, user: AuthenticatedUser, asset_id: uuid.UUID, *, role_check
) -> tuple[VisualAsset, CreativeItem]:
    asset = repository.get_asset(session, asset_id)
    if asset is None:
        raise _not_found()
    item = repository.get_item(session, asset.creative_item_id)
    if item is None:
        raise _not_found()
    membership = repository.get_membership(session, user.id, item.brand_id)
    if membership is None:
        raise _not_found()
    role_check(membership)
    return asset, item


async def _compensate_remove(storage: StoragePort, path: str) -> None:
    try:
        await storage.remove_object(path=path)
    except Exception as exc:
        logger.warning(
            "Storage compensation (remove_object) failed after a transaction rollback: %s",
            type(exc).__name__,
        )


def _insert_asset_locked(
    session: Session,
    item: CreativeItem,
    actor_id: uuid.UUID,
    *,
    version: int,
    path: str,
    content_type: str,
) -> VisualAsset:
    locked = repository.lock_item(session, item.id)
    if locked is None:
        raise _not_found()
    policies.require_uploadable_state(locked.workflow_status, locked.id)
    asset = repository.insert_asset(
        session,
        creative_item_id=locked.id,
        version=version,
        storage_path=path,
        metadata={"content_type": content_type},
        uploaded_by=actor_id,
    )
    session.flush()
    # Guarded by require_uploadable_state above: only CONTENT_APPROVED (first
    # visual) or VISUAL_CHANGES_REQUESTED (correction) reach here, and both
    # transition to PENDING_VISUAL_REVIEW (spec: first upload + reopened queue).
    locked.workflow_status = CreativeWorkflowStatus.PENDING_VISUAL_REVIEW
    repository.add_workflow_event(
        session,
        locked.id,
        repository.UPLOADED_EVENT,
        actor_id,
        {"visual_asset_id": str(asset.id), "version": version},
    )
    session.flush()
    return asset


async def upload(
    session: Session,
    user: AuthenticatedUser,
    item_id: uuid.UUID,
    *,
    content: bytes,
    storage: StoragePort | None,
    settings: Settings,
    tracer: Tracer,
) -> VisualAssetOut:
    item = _resolve_item_for_upload(session, user, item_id)
    if storage is None:
        raise StorageNotConfiguredError("visual.upload")
    validated = validation.validate_upload(content, max_bytes=settings.storage_max_upload_bytes)

    start = time.perf_counter()
    version = repository.max_asset_version(session, item.id) + 1
    path = _visual_path(item.brand_id, item.id, version, validated.extension)
    await storage.put_object(path=path, content=content, content_type=validated.content_type)
    try:
        asset = _insert_asset_locked(
            session, item, user.id, version=version, path=path, content_type=validated.content_type
        )
        session.commit()
    except IntegrityError:
        # Race escaped the lock (unique item+version): rollback, compensate the
        # orphaned object at the lost path, recompute the version and retry once.
        session.rollback()
        await _compensate_remove(storage, path)
        locked = repository.lock_item(session, item.id)
        if locked is None:
            raise _not_found() from None
        version = repository.max_asset_version(session, item.id) + 1
        path = _visual_path(item.brand_id, item.id, version, validated.extension)
        await storage.put_object(path=path, content=content, content_type=validated.content_type)
        asset = _insert_asset_locked(
            session, item, user.id, version=version, path=path, content_type=validated.content_type
        )
        session.commit()
    except InvalidWorkflowTransitionError:
        session.rollback()
        await _compensate_remove(storage, path)
        raise
    except Exception:
        session.rollback()
        await _compensate_remove(storage, path)
        raise

    signed = await storage.signed_url(
        path=asset.storage_path, ttl_seconds=settings.storage_signed_url_ttl_seconds
    )
    await _emit(
        tracer,
        CapabilitySpan(
            entity=f"creative_item:{item.id}",
            model=None,
            latency_ms=(time.perf_counter() - start) * 1000.0,
            operation="visual.upload",
            brand_id=str(item.brand_id),
            entity_type="visual_asset",
            entity_id=str(asset.id),
        ),
    )
    return _to_asset_out(asset, signed)


async def list_assets(
    session: Session,
    user: AuthenticatedUser,
    item_id: uuid.UUID,
    *,
    storage: StoragePort | None,
    settings: Settings,
) -> VisualAssetList:
    item = _resolve_reader_item(session, user, item_id)
    assets = repository.list_assets(session, item.id)
    if assets and storage is None:
        # Only a real asset needs a signed URL; an empty list is always
        # servable, storage-configured or not (no signing work to do).
        raise StorageNotConfiguredError("visual.list_assets")
    out = []
    for asset in assets:
        assert storage is not None  # guarded above whenever assets is non-empty
        signed = await storage.signed_url(
            path=asset.storage_path, ttl_seconds=settings.storage_signed_url_ttl_seconds
        )
        out.append(_to_asset_out(asset, signed))
    return VisualAssetList(assets=out)


def _compose_audit_request(item: CreativeItem, context: knowledge_service.BuiltContext) -> str:
    lines = [
        f"ITEM TITLE: {item.title}",
        f"BRAND CONTEXT (Brand DNA version {context.brand_dna_version_id})",
        "MANDATORY VISUAL RULES (always apply):",
        *[
            f"- rule_id={rule.id} [{rule.section}/{rule.rule_type}] {rule.content}"
            for rule in context.mandatory
        ],
        "SEMANTIC VISUAL CONTEXT (ranked for this task):",
        *[
            f"- rule_id={rule.id} [{rule.section}/{rule.rule_type}] {rule.content}"
            for rule in context.semantic
        ],
        "Respond with JSON matching the VisualAuditResult contract; findings must "
        "cite only rule_id values present above, severity in low|medium|high and "
        "status in pass|fail.",
    ]
    return "\n".join(lines)


async def run_audit(
    session: Session,
    user: AuthenticatedUser,
    asset_id: uuid.UUID,
    *,
    vision_adapter: VisionModel | None,
    embedding_adapter: EmbeddingModel | None,
    storage: StoragePort | None,
    settings: Settings,
    tracer: Tracer,
) -> VisualAuditOut:
    asset, item = _resolve_asset(
        session, user, asset_id, role_check=policies.require_audit_trigger
    )
    if storage is None:
        raise StorageNotConfiguredError("visual.audit")

    start = time.perf_counter()
    # Fail-safe context first (spec: no mandatory visual context -> 503, no
    # model call, no persisted audit); the Vision call only happens after.
    context = await knowledge_service.build_context(
        session,
        brand_id=item.brand_id,
        task="VISUAL",
        query=f"Visual compliance audit for creative item: {item.title}",
        embedding_adapter=embedding_adapter,
        tracer=tracer,
    )
    image_ref = await storage.signed_url(
        path=asset.storage_path, ttl_seconds=settings.storage_signed_url_ttl_seconds
    )
    # Cross-consumption (012-brand-assets task 3.1): resolve the brand's
    # PRIMARY_LOGO as comparison context through brand-assets' own read path
    # -- this module never opens its own storage access for it, it reuses the
    # exact `storage`/`settings` already injected here. Best-effort: a brand
    # with no PRIMARY_LOGO yet (or a lookup failure) never blocks the audit.
    try:
        primary_logo = await brand_assets_service.get_primary_logo(
            session, item.brand_id, storage=storage, settings=settings
        )
    except Exception as exc:
        logger.warning("Brand asset lookup failed during visual audit: %s", type(exc).__name__)
        primary_logo = None
    request = _compose_audit_request(item, context)
    try:
        run = await run_capability(
            prompt_id=AUDIT_PROMPT_ID,
            adapter=vision_adapter,
            tracer=tracer,
            contract=VisualAuditResult,
            request=request,
            image_ref=image_ref,
            entity=f"visual_asset:{asset.id}",
            brand_id=str(item.brand_id),
            entity_type="visual_asset",
            entity_id=str(asset.id),
        )
    except AIOutputValidationError as exc:
        raise VisionOutputInvalidError(exc.cause) from exc

    score = policies.compute_score(run.output.findings)
    applied_context_snapshot = {
        "brand_dna_version_id": str(context.brand_dna_version_id),
        "mandatory_rule_count": len(context.mandatory),
        "semantic_rule_count": len(context.semantic),
        # Durable reference (never the transient signed URL) evidencing the
        # brand-assets read path was consulted; null when the brand has no
        # PRIMARY_LOGO yet.
        "brand_primary_logo_asset_id": str(primary_logo.id) if primary_logo else None,
    }
    audit = repository.insert_audit(
        session,
        visual_asset_id=asset.id,
        brand_dna_version_id=context.brand_dna_version_id,
        checks=[check.model_dump(mode="json") for check in run.output.checks],
        findings=[finding.model_dump(mode="json") for finding in run.output.findings],
        score=score,
        summary=run.output.summary,
        applied_context=applied_context_snapshot,
        langfuse_trace_id=run.metadata.trace_id,
    )
    session.commit()

    await _emit(
        tracer,
        CapabilitySpan(
            entity=f"visual_asset:{asset.id}",
            model=run.metadata.model,
            latency_ms=(time.perf_counter() - start) * 1000.0,
            operation="visual.audit",
            summary=TraceSummary(
                contract="VisualAuditResult",
                ok=True,
                check_count=len(run.output.checks),
                finding_count=len(run.output.findings),
            ),
            brand_id=str(item.brand_id),
            entity_type="visual_audit",
            entity_id=str(audit.id),
        ),
    )
    return _to_audit_out(audit)


def get_latest_audit(
    session: Session, user: AuthenticatedUser, asset_id: uuid.UUID
) -> VisualAuditOut:
    asset, _item = _resolve_asset(session, user, asset_id, role_check=policies.require_reader)
    audit = repository.latest_audit(session, asset.id)
    if audit is None:
        raise _not_found()
    return _to_audit_out(audit)


async def queue(
    session: Session,
    user: AuthenticatedUser,
    *,
    storage: StoragePort | None,
    settings: Settings,
) -> QueueOut:
    brand_ids = repository.list_membership_brand_ids(session, user.id)
    items_out: list[QueueItemOut] = []
    for item in repository.queue(session, brand_ids):
        membership = repository.get_membership(session, user.id, item.brand_id)
        policies.require_queue_reader(membership)
        asset = repository.latest_asset(session, item.id)
        if asset is None:
            continue  # PENDING_VISUAL_REVIEW implies an asset exists; skip defensively
        if storage is None:
            raise StorageNotConfiguredError("visual.queue")
        signed = await storage.signed_url(
            path=asset.storage_path, ttl_seconds=settings.storage_signed_url_ttl_seconds
        )
        audit = repository.latest_audit(session, asset.id)
        items_out.append(
            QueueItemOut(
                item=_to_item_summary(session, item),
                asset=_to_asset_out(asset, signed),
                latest_audit=_to_audit_out(audit) if audit is not None else None,
            )
        )
    return QueueOut(items=items_out)


async def history(
    session: Session,
    user: AuthenticatedUser,
    item_id: uuid.UUID,
    *,
    storage: StoragePort | None,
    settings: Settings,
) -> VisualAuditHistoryOut:
    item = _resolve_reader_item(session, user, item_id)
    assets = repository.list_assets(session, item.id)
    if assets and storage is None:
        # Only a real asset needs a signed URL; an item with no visuals yet
        # has an empty (and always servable) history.
        raise StorageNotConfiguredError("visual.history")
    entries: list[VisualHistoryEntryOut] = []
    for asset in assets:
        assert storage is not None  # guarded above whenever assets is non-empty
        signed = await storage.signed_url(
            path=asset.storage_path, ttl_seconds=settings.storage_signed_url_ttl_seconds
        )
        audits = repository.list_audits(session, asset.id)
        reviews: list[VisualReview] = []
        for audit in audits:
            reviews.extend(repository.list_reviews(session, audit.id))
        entries.append(
            VisualHistoryEntryOut(
                asset=_to_asset_out(asset, signed),
                audits=[_to_audit_out(a) for a in audits],
                reviews=[_to_review_out(r) for r in reviews],
            )
        )
    return VisualAuditHistoryOut(item=_to_item_summary(session, item), entries=entries)


def approve(
    session: Session, user: AuthenticatedUser, audit_id: uuid.UUID, payload: ApproveIn
) -> DecisionOut:
    return _decide(
        session,
        user,
        audit_id,
        decision=VisualReviewDecision.APPROVED,
        dest_status=CreativeWorkflowStatus.FINAL_APPROVED,
        event_type=repository.APPROVED_EVENT,
        feedback=None,
        exception_accepted=payload.exception_accepted,
    )


def request_changes(
    session: Session, user: AuthenticatedUser, audit_id: uuid.UUID, payload: RequestChangesIn
) -> DecisionOut:
    return _decide(
        session,
        user,
        audit_id,
        decision=VisualReviewDecision.CHANGES_REQUESTED,
        dest_status=CreativeWorkflowStatus.VISUAL_CHANGES_REQUESTED,
        event_type=repository.CHANGES_REQUESTED_EVENT,
        feedback=payload.feedback,
        exception_accepted=False,
    )


def _decide(
    session: Session,
    user: AuthenticatedUser,
    audit_id: uuid.UUID,
    *,
    decision: VisualReviewDecision,
    dest_status: CreativeWorkflowStatus,
    event_type: str,
    feedback: str | None,
    exception_accepted: bool,
) -> DecisionOut:
    audit = repository.get_audit(session, audit_id)
    if audit is None:
        raise _not_found()
    asset = repository.get_asset(session, audit.visual_asset_id)
    if asset is None:
        raise _not_found()
    item = repository.get_item(session, asset.creative_item_id)
    if item is None:
        raise _not_found()
    membership = repository.get_membership(session, user.id, item.brand_id)
    if membership is None:
        raise _not_found()
    policies.require_reviewer(membership)

    evidence: dict | None = None
    if decision == VisualReviewDecision.APPROVED:
        findings = [Finding.model_validate(f) for f in audit.findings]
        policies.require_exception_for_high_findings(
            findings, exception_accepted=exception_accepted
        )
        high = policies.high_fail_findings(findings)
        if high:
            evidence = {
                "high_findings": [
                    {
                        "rule_id": finding.rule_id,
                        "category": finding.category,
                        "severity": finding.severity,
                    }
                    for finding in high
                ]
            }

    try:
        result = _decide_locked(
            session,
            user,
            item,
            audit,
            decision=decision,
            dest_status=dest_status,
            event_type=event_type,
            feedback=feedback,
            exception_accepted=exception_accepted,
            evidence=evidence,
        )
        session.commit()
    except InvalidWorkflowTransitionError:
        session.rollback()
        raise
    except IntegrityError:
        # SQLite's SELECT-FOR-UPDATE is a no-op, so two concurrent decisions
        # can both read PENDING_VISUAL_REVIEW before either commits; same
        # recovery as governance: rollback and re-run once, the retry now
        # sees the winner's committed state and takes the idempotent path.
        session.rollback()
        result = _decide_locked(
            session,
            user,
            item,
            audit,
            decision=decision,
            dest_status=dest_status,
            event_type=event_type,
            feedback=feedback,
            exception_accepted=exception_accepted,
            evidence=evidence,
        )
        session.commit()
    return result


def _decide_locked(
    session: Session,
    user: AuthenticatedUser,
    item: CreativeItem,
    audit: VisualAudit,
    *,
    decision: VisualReviewDecision,
    dest_status: CreativeWorkflowStatus,
    event_type: str,
    feedback: str | None,
    exception_accepted: bool,
    evidence: dict | None,
) -> DecisionOut:
    locked = repository.lock_item(session, item.id)
    if locked is None:
        raise _not_found()

    existing = repository.get_review(session, audit.id, user.id, decision)
    if existing is not None:
        # Idempotent retry: same reviewer + same audit + same decision.
        return DecisionOut(item=_to_item_summary(session, locked), review=_to_review_out(existing))

    if locked.workflow_status != CreativeWorkflowStatus.PENDING_VISUAL_REVIEW:
        raise InvalidWorkflowTransitionError(
            "Creative item is not pending visual review",
            {"item_id": locked.id, "workflow_status": locked.workflow_status.value},
        )

    locked.workflow_status = dest_status
    review = repository.insert_review(
        session,
        visual_audit_id=audit.id,
        reviewer_id=user.id,
        decision=decision,
        feedback=feedback,
        exception_accepted=exception_accepted,
        evidence=evidence,
    )
    repository.add_workflow_event(
        session,
        locked.id,
        event_type,
        user.id,
        {
            "visual_asset_id": str(audit.visual_asset_id),
            "visual_audit_id": str(audit.id),
            "review_id": str(review.id),
        },
    )
    session.flush()
    return DecisionOut(item=_to_item_summary(session, locked), review=_to_review_out(review))
