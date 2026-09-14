"""Application service for creative: item/version lifecycle, submit transition and guards.

Cross-brand items answer 404 (UUID resources must not confirm existence);
role denials for members answer 403. Versions are insert-only: no update
path exists, which is the immutability invariant behind "submitted version
stays frozen" (WORKFLOWS.md). The only post-insert write is the consistency
audit projection (`repository.record_consistency_result`), which never touches
content columns.

AI operations (generate/regenerate/consistency-check) follow the same
provider-safety shape as knowledge sync: guards and the hybrid context are
resolved first, provider calls happen with no open transaction across them,
and the version insert is a short locked transaction afterwards.
"""

import json
import uuid
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai import scoring
from app.ai.contracts import ConsistencyResult, CreativeOutput
from app.ai.ports import EmbeddingModel, TextModel
from app.ai.runner import run_capability
from app.brand_dna.models import KnowledgeStatus
from app.creative import policies, repository
from app.creative.models import (
    CreativeItem,
    CreativeItemType,
    CreativeVersion,
    CreativeVersionOrigin,
    CreativeWorkflowStatus,
)
from app.creative.policies import InvalidWorkflowTransitionError
from app.creative.schemas import (
    AppliedContextOut,
    ItemCreateIn,
    ItemList,
    ItemOut,
    ItemSummary,
    PipelineOut,
    SubmitIn,
    VersionCreateIn,
    VersionList,
    VersionOut,
    VersionSummary,
)
from app.identity.auth import AuthenticatedUser
from app.knowledge import service as knowledge_service
from app.knowledge.errors import KnowledgeNotAvailableError
from app.observability.ports import Tracer

_TYPE_TO_CONTENT_TYPE = {
    CreativeItemType.PRODUCT_DESCRIPTION: "product_description",
    CreativeItemType.VIDEO_SCRIPT: "video_script",
    CreativeItemType.IMAGE_PROMPT: "image_prompt",
}

# Task-specific retrieval scopes (AI_SYSTEM.md): text tasks rank TEXT chunks,
# image prompts rank VISUAL chunks; mandatory rules always enter both.
_TYPE_TO_TASK: dict[CreativeItemType, Literal["TEXT", "VISUAL"]] = {
    CreativeItemType.PRODUCT_DESCRIPTION: "TEXT",
    CreativeItemType.VIDEO_SCRIPT: "TEXT",
    CreativeItemType.IMAGE_PROMPT: "VISUAL",
}

_TYPE_TO_PROMPT_ID = {
    CreativeItemType.PRODUCT_DESCRIPTION: "creative.product_description.v1",
    CreativeItemType.VIDEO_SCRIPT: "creative.video_script.v1",
    CreativeItemType.IMAGE_PROMPT: "creative.image_prompt.v1",
}
CONSISTENCY_PROMPT_ID = "consistency.text.v1"

# Bounded retrieval query: brand context ranking needs a discriminative string,
# not the whole payload (cost control; chunker-capped contents do the rest).
_MAX_QUERY_CHARS = 4000


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creative item not found")


def _to_version_out(version: CreativeVersion) -> VersionOut:
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
        output=(
            CreativeOutput.model_validate(version.output) if version.output is not None else None
        ),
        applied_rule_ids=version.applied_rule_ids or [],
        consistency_result=version.consistency_result,
        langfuse_trace_id=version.langfuse_trace_id,
    )


def _to_version_summary(version: CreativeVersion) -> VersionSummary:
    return VersionSummary(
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
    )


def _to_item_summary(item: CreativeItem, latest_version_number: int) -> ItemSummary:
    return ItemSummary(
        id=item.id,
        brand_id=item.brand_id,
        type=item.type,
        title=item.title,
        workflow_status=item.workflow_status,
        created_by=item.created_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
        latest_version=latest_version_number,
    )


def _to_item_out(item: CreativeItem, latest: CreativeVersion | None) -> ItemOut:
    return ItemOut(
        **_to_item_summary(item, latest.version if latest else 0).model_dump(),
        current_version=_to_version_out(latest) if latest else None,
    )


def _resolve_item(
    session: Session, user: AuthenticatedUser, item_id: uuid.UUID, *, writer: bool
) -> CreativeItem:
    """Resolve item + membership; 404 for missing OR non-member (no existence leak)."""
    item = repository.get_item(session, item_id)
    if item is None:
        raise _not_found()
    membership = repository.get_membership(session, user.id, item.brand_id)
    if membership is None:
        raise _not_found()
    if writer:
        policies.require_writer(membership)
    else:
        policies.require_reader(membership)
    return item


def create_item(session: Session, user: AuthenticatedUser, payload: ItemCreateIn) -> ItemOut:
    membership = repository.get_membership(session, user.id, payload.brand_id)
    policies.require_writer(membership)
    item = CreativeItem(
        id=uuid.uuid4(),
        brand_id=payload.brand_id,
        type=payload.type,
        title=payload.title,
        workflow_status=CreativeWorkflowStatus.DRAFT,
        created_by=user.id,
    )
    # Version 1 carries the brief; content arrives with the first edit/generation.
    first = CreativeVersion(
        id=uuid.uuid4(),
        creative_item_id=item.id,
        version=1,
        brand_dna_version_id=repository.get_active_brand_dna_version_id(
            session, payload.brand_id
        ),
        origin=CreativeVersionOrigin.HUMAN_EDIT,
        brief=payload.brief or {},
        output=None,
        applied_rule_ids=[],
        created_by=user.id,
    )
    session.add(item)
    session.add(first)
    session.commit()
    return _to_item_out(item, first)


def list_items(
    session: Session, user: AuthenticatedUser, brand_id: uuid.UUID | None
) -> ItemList:
    if brand_id is not None:
        membership = repository.get_membership(session, user.id, brand_id)
        policies.require_reader(membership)
        brand_ids = [brand_id]
    else:
        brand_ids = repository.list_membership_brand_ids(session, user.id)
    summaries = []
    for item in repository.list_items(session, brand_ids):
        latest = repository.latest_version(session, item.id)
        summaries.append(_to_item_summary(item, latest.version if latest else 0))
    return ItemList(items=summaries)


def pipeline(session: Session, user: AuthenticatedUser, brand_id: uuid.UUID) -> PipelineOut:
    """Content Pipeline breakdown (change 014): membership-first, then the real
    7-state count — no client input decides which brand is authorized."""
    membership = repository.get_membership(session, user.id, brand_id)
    policies.require_reader(membership)
    counts = repository.count_by_workflow_status(session, brand_id)
    return PipelineOut(brand_id=brand_id, counts=counts, total=sum(counts.values()))


def get_item(session: Session, user: AuthenticatedUser, item_id: uuid.UUID) -> ItemOut:
    item = _resolve_item(session, user, item_id, writer=False)
    return _to_item_out(item, repository.latest_version(session, item.id))


def list_versions(
    session: Session, user: AuthenticatedUser, item_id: uuid.UUID
) -> VersionList:
    item = _resolve_item(session, user, item_id, writer=False)
    versions = repository.get_versions(session, item.id)
    return VersionList(versions=[_to_version_summary(v) for v in versions])


def get_version_detail(
    session: Session, user: AuthenticatedUser, item_id: uuid.UUID, version_id: uuid.UUID
) -> VersionOut:
    """Full read-only detail of one version (spec 04: listar/ver versiones).

    Same read policy as the rest of the module: any brand member reads;
    404 for missing item/version, foreign version or non-member.
    """
    item = _resolve_item(session, user, item_id, writer=False)
    version = repository.get_version_by_id(session, item.id, version_id)
    if version is None:
        raise _not_found()
    return _to_version_out(version)


def applied_context(
    session: Session, user: AuthenticatedUser, item_id: uuid.UUID
) -> AppliedContextOut:
    item = _resolve_item(session, user, item_id, writer=False)
    latest = repository.latest_version(session, item.id)
    if latest is None:
        raise _not_found()
    return AppliedContextOut(
        creative_item_id=item.id,
        version_id=latest.id,
        version=latest.version,
        brand_dna_version_id=latest.brand_dna_version_id,
        applied_rule_ids=latest.applied_rule_ids or [],
    )


def _require_synced_knowledge(session: Session, brand_id: uuid.UUID) -> None:
    """Spec 04 guard: generate/regenerate/check/submit require SYNCED knowledge.

    Stricter than knowledge's own servable set (SYNCED|OUTDATED) on purpose:
    creative operations must run against the exact published Brand Knowledge,
    never against chunks superseded by an unpublished draft. Raises the domain
    error mapped to the 503 KNOWLEDGE_NOT_AVAILABLE envelope.
    """
    active = repository.get_active_brand_dna_version(session, brand_id)
    if active is None:
        raise KnowledgeNotAvailableError("No active Brand DNA version")
    if active.knowledge_status != KnowledgeStatus.SYNCED:
        raise KnowledgeNotAvailableError(
            f"Brand Knowledge is {active.knowledge_status.value}; SYNCED is required"
        )


def _flatten_text_values(node: object, out: list[str]) -> None:
    if isinstance(node, str) and node:
        out.append(node)
    elif isinstance(node, (list, tuple)):
        for child in node:
            _flatten_text_values(child, out)
    elif isinstance(node, dict):
        for child in node.values():
            _flatten_text_values(child, out)


def _retrieval_query(item: CreativeItem, version: CreativeVersion) -> str:
    values: list[str] = [item.title]
    _flatten_text_values(version.brief, values)
    if version.output is not None:
        _flatten_text_values(version.output, values)
    return " ".join(values)[:_MAX_QUERY_CHARS]


def _output_body(output: CreativeOutput) -> str:
    if output.content is not None:
        return output.content
    return "\n".join(
        f"{section.heading}: {section.body}" for section in output.structured_sections or []
    )


def _context_section(context: knowledge_service.BuiltContext) -> list[str]:
    lines = [f"BRAND CONTEXT (Brand DNA version {context.brand_dna_version_id})"]
    lines.append("MANDATORY RULES (always apply):")
    lines.extend(
        f"- rule_id={rule.id} [{rule.section}/{rule.rule_type}] {rule.content}"
        for rule in context.mandatory
    )
    lines.append("SEMANTIC CONTEXT (ranked for this task):")
    lines.extend(
        f"- rule_id={rule.id} [{rule.section}/{rule.rule_type}] {rule.content}"
        for rule in context.semantic
    )
    return lines


def _compose_generate_request(
    item: CreativeItem, version: CreativeVersion, context: knowledge_service.BuiltContext
) -> str:
    lines = [
        f"ITEM TYPE: {item.type.value}",
        f"ITEM TITLE: {item.title}",
        f"BRIEF: {json.dumps(version.brief, sort_keys=True, default=str)}",
        *_context_section(context),
        "Respond with JSON matching the CreativeOutput contract; applied_rule_ids must "
        "cite only the rule_id values actually applied.",
    ]
    return "\n".join(lines)


def _compose_check_request(
    item: CreativeItem, version: CreativeVersion, context: knowledge_service.BuiltContext
) -> str:
    output = CreativeOutput.model_validate(version.output)
    lines = [
        f"ITEM TYPE: {item.type.value}",
        f"ITEM TITLE: {item.title}",
        "CONTENT TO CHECK:",
        _output_body(output),
        *_context_section(context),
        "Respond with JSON matching the ConsistencyResult contract.",
    ]
    return "\n".join(lines)


def _verified_applied_rule_ids(
    output: CreativeOutput, context: knowledge_service.BuiltContext
) -> list[str]:
    """Never persist fabricated rule refs: keep only ids present in the retrieved context.

    When the model cites nothing real, the mandatory rules remain the honest
    floor — mandatory context always applies by construction (AI_SYSTEM.md).
    """
    retrieved = {str(rule.id) for rule in (*context.mandatory, *context.semantic)}
    verified = [rule_id for rule_id in output.applied_rule_ids if rule_id in retrieved]
    if not verified:
        verified = [str(rule.id) for rule in context.mandatory]
    return verified


def _insert_ai_version_locked(
    session: Session,
    item: CreativeItem,
    actor_id: uuid.UUID,
    *,
    version_id: uuid.UUID,
    output: CreativeOutput,
    origin: CreativeVersionOrigin,
    brand_dna_version_id: uuid.UUID,
    trace_id: str | None,
) -> CreativeVersion:
    if repository.lock_item(session, item.id) is None:
        raise _not_found()
    if item.workflow_status not in policies.EDITABLE_STATUSES:
        raise InvalidWorkflowTransitionError(
            "Creative item cannot be generated from its current state",
            {"item_id": item.id, "workflow_status": item.workflow_status.value},
        )
    previous = repository.latest_version(session, item.id)
    version = CreativeVersion(
        id=version_id,
        creative_item_id=item.id,
        version=repository.max_version(session, item.id) + 1,
        # The exact Brand DNA version whose knowledge built the context, not
        # just "ACTIVE at insert time" (spec 04 applied-context invariant).
        brand_dna_version_id=brand_dna_version_id,
        origin=origin,
        brief=previous.brief if previous else {},
        output=output.model_dump(mode="json"),
        applied_rule_ids=output.applied_rule_ids,
        langfuse_trace_id=trace_id,
        created_by=actor_id,
    )
    session.add(version)
    session.flush()
    return version


async def generate(
    session: Session,
    user: AuthenticatedUser,
    item_id: uuid.UUID,
    *,
    text_adapter: TextModel | None,
    embedding_adapter: EmbeddingModel | None,
    tracer: Tracer,
    regenerate: bool = False,
) -> VersionOut:
    """Generate (or regenerate) a new AI version from retrieved Brand Knowledge.

    Guards and context run before any provider call; the provider calls run
    with no open write transaction; the insert is a short locked transaction
    afterwards (same provider-safety shape as knowledge sync). A validation
    failure of the structured output never persists a version.
    """
    item = _resolve_item(session, user, item_id, writer=True)
    if item.workflow_status not in policies.EDITABLE_STATUSES:
        raise InvalidWorkflowTransitionError(
            "Creative item cannot be generated from its current state",
            {"item_id": item.id, "workflow_status": item.workflow_status.value},
        )
    _require_synced_knowledge(session, item.brand_id)
    latest = repository.latest_version(session, item.id)
    assert latest is not None  # item creation always seeds version 1
    context = await knowledge_service.build_context(
        session,
        brand_id=item.brand_id,
        task=_TYPE_TO_TASK[item.type],
        query=_retrieval_query(item, latest),
        embedding_adapter=embedding_adapter,
        tracer=tracer,
    )
    # Pre-generated id: binds the capability span to the version this call creates.
    version_id = uuid.uuid4()
    run = await run_capability(
        prompt_id=_TYPE_TO_PROMPT_ID[item.type],
        adapter=text_adapter,
        tracer=tracer,
        contract=CreativeOutput,
        request=_compose_generate_request(item, latest, context),
        entity=f"creative_item:{item.id}",
        brand_id=str(item.brand_id),
        entity_type="creative_version",
        entity_id=str(version_id),
    )
    verified = _verified_applied_rule_ids(run.output, context)
    output = run.output.model_copy(update={"applied_rule_ids": verified})
    origin = (
        CreativeVersionOrigin.AI_REGENERATED if regenerate else CreativeVersionOrigin.AI_GENERATED
    )
    try:
        version = _insert_ai_version_locked(
            session,
            item,
            user.id,
            version_id=version_id,
            output=output,
            origin=origin,
            brand_dna_version_id=context.brand_dna_version_id,
            trace_id=run.metadata.trace_id,
        )
        session.commit()
    except InvalidWorkflowTransitionError:
        session.rollback()
        raise
    except IntegrityError:
        # Race escaped the lock (unique item+version): rollback, re-read and re-apply.
        session.rollback()
        locked = repository.lock_item(session, item.id)
        if locked is None:
            raise _not_found() from None
        version = _insert_ai_version_locked(
            session,
            item,
            user.id,
            version_id=version_id,
            output=output,
            origin=origin,
            brand_dna_version_id=context.brand_dna_version_id,
            trace_id=run.metadata.trace_id,
        )
        session.commit()
    return _to_version_out(version)


async def consistency_check(
    session: Session,
    user: AuthenticatedUser,
    item_id: uuid.UUID,
    *,
    text_adapter: TextModel | None,
    embedding_adapter: EmbeddingModel | None,
    tracer: Tracer,
) -> VersionOut:
    """Check the latest version's content against retrieved Brand Knowledge.

    Persists only the audit projection (ConsistencyResult + backend-computed
    score + trace id inside the result payload); the version's content columns
    are never touched. No workflow transition is involved.
    """
    item = _resolve_item(session, user, item_id, writer=True)
    version = repository.latest_version(session, item.id)
    if version is None:
        raise _not_found()
    if version.output is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Latest version has no content to check",
        )
    _require_synced_knowledge(session, item.brand_id)
    context = await knowledge_service.build_context(
        session,
        brand_id=item.brand_id,
        task=_TYPE_TO_TASK[item.type],
        query=_retrieval_query(item, version),
        embedding_adapter=embedding_adapter,
        tracer=tracer,
    )
    run = await run_capability(
        prompt_id=CONSISTENCY_PROMPT_ID,
        adapter=text_adapter,
        tracer=tracer,
        contract=ConsistencyResult,
        request=_compose_check_request(item, version, context),
        entity=f"creative_version:{version.id}",
        brand_id=str(item.brand_id),
        entity_type="creative_version",
        entity_id=str(version.id),
    )
    # Backend-computed score (AI_SYSTEM.md): the model classifies, we score.
    score = scoring.consistency_score(run.output)
    # trace_id rides inside the result payload: version.langfuse_trace_id keeps
    # the trace of the operation that CREATED the version, not the audit.
    result_payload = {**run.output.model_dump(mode="json"), "trace_id": run.metadata.trace_id}
    try:
        repository.record_consistency_result(
            session,
            version.id,
            consistency_result=result_payload,
            consistency_score=score,
        )
        session.commit()
    except IntegrityError:
        session.rollback()
        raise
    return _to_version_out(version)


def _insert_next_version(
    session: Session,
    item: CreativeItem,
    actor_id: uuid.UUID,
    payload: VersionCreateIn,
    origin: CreativeVersionOrigin,
) -> CreativeVersion:
    previous = repository.latest_version(session, item.id)
    expected_content_type = _TYPE_TO_CONTENT_TYPE[item.type]
    if payload.output.content_type != expected_content_type:
        raise HTTPException(
            status_code=422,
            detail=f"output.content_type must be {expected_content_type} for this item type",
        )
    version = CreativeVersion(
        id=uuid.uuid4(),
        creative_item_id=item.id,
        version=repository.max_version(session, item.id) + 1,
        brand_dna_version_id=repository.get_active_brand_dna_version_id(session, item.brand_id),
        origin=origin,
        brief=payload.brief if payload.brief is not None else (previous.brief if previous else {}),
        output=payload.output.model_dump(mode="json"),
        applied_rule_ids=payload.output.applied_rule_ids,
        created_by=actor_id,
    )
    session.add(version)
    session.flush()
    return version


def create_version(
    session: Session, user: AuthenticatedUser, item_id: uuid.UUID, payload: VersionCreateIn
) -> VersionOut:
    item = _resolve_item(session, user, item_id, writer=True)
    try:
        version = _create_version_locked(session, user, item, payload)
        session.commit()
    except InvalidWorkflowTransitionError:
        session.rollback()
        raise
    except IntegrityError:
        # Race escaped the lock (unique item+version): rollback, re-read and re-apply.
        session.rollback()
        item = repository.lock_item(session, item.id)
        if item is None:
            raise _not_found() from None
        version = _create_version_locked(session, user, item, payload)
        session.commit()
    return _to_version_out(version)


def _create_version_locked(
    session: Session, user: AuthenticatedUser, item: CreativeItem, payload: VersionCreateIn
) -> CreativeVersion:
    if repository.lock_item(session, item.id) is None:
        raise _not_found()
    if item.workflow_status not in policies.EDITABLE_STATUSES:
        raise InvalidWorkflowTransitionError(
            "Creative item cannot be edited from its current state",
            {"item_id": item.id, "workflow_status": item.workflow_status.value},
        )
    return _insert_next_version(session, item, user.id, payload, CreativeVersionOrigin.HUMAN_EDIT)


def submit(
    session: Session, user: AuthenticatedUser, item_id: uuid.UUID, payload: SubmitIn
) -> ItemOut:
    item = _resolve_item(session, user, item_id, writer=True)
    try:
        result = _submit_locked(session, user, item, payload)
        session.commit()
    except (InvalidWorkflowTransitionError, KnowledgeNotAvailableError):
        session.rollback()
        raise
    except IntegrityError:
        session.rollback()
        item = repository.lock_item(session, item.id)
        if item is None:
            raise _not_found() from None
        result = _submit_locked(session, user, item, payload)
        session.commit()
    return result


def _submit_locked(
    session: Session, user: AuthenticatedUser, item: CreativeItem, payload: SubmitIn
) -> ItemOut:
    if repository.lock_item(session, item.id) is None:
        raise _not_found()
    version = repository.get_version_by_id(session, item.id, payload.version_id)
    if version is None:
        raise _not_found()
    if item.workflow_status == CreativeWorkflowStatus.PENDING_CONTENT_REVIEW:
        last_submitted = repository.last_submitted_version_id(session, item.id)
        if last_submitted == version.id:
            # Idempotent retry of the same submit: return the current state.
            return _to_item_out(item, repository.latest_version(session, item.id))
        raise InvalidWorkflowTransitionError(
            "Creative item is already pending content review for another version",
            {"item_id": item.id, "requested_version_id": version.id},
        )
    if item.workflow_status not in policies.EDITABLE_STATUSES:
        raise InvalidWorkflowTransitionError(
            "Creative item cannot be submitted from its current state",
            {"item_id": item.id, "workflow_status": item.workflow_status.value},
        )
    if payload.version_id in repository.submitted_version_ids(session, item.id):
        raise InvalidWorkflowTransitionError(
            "Version was already submitted; create a new version to resubmit",
            {"item_id": item.id, "requested_version_id": version.id},
        )
    if version.output is None:
        # A brief-only version (the initial v1) has nothing for reviewers to
        # judge: content must be generated or written before submission.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Version has no content to submit; generate or edit content first",
        )
    # WORKFLOWS.md content submission: knowledge availability is verified before
    # any mutation; the 503 KNOWLEDGE_NOT_AVAILABLE envelope answers otherwise.
    _require_synced_knowledge(session, item.brand_id)
    item.workflow_status = CreativeWorkflowStatus.PENDING_CONTENT_REVIEW
    repository.add_workflow_event(
        session,
        item.id,
        repository.SUBMITTED_EVENT,
        user.id,
        {"version_id": str(version.id), "version": version.version},
    )
    session.flush()
    return _to_item_out(item, repository.latest_version(session, item.id))
