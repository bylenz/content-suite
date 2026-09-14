"""Observability facade service (change 009).

Authorization is membership-first and backend-only: the service resolves the
user's brand memberships BEFORE any repository call, and every read narrows to
that authorized set. `brand_id` and roles from the client are never authority.
Facade reads emit sanitized structured logs only — no spans, no new index rows
(no recursion) — and never log secrets or payloads.
"""

import logging
import time
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.identity.auth import AuthenticatedUser
from app.identity.models import BrandRole
from app.identity.policies import authorize_brand_action
from app.identity.repository import get_membership, list_memberships
from app.observability.ports import TraceQuery, TraceRecordRepository
from app.observability.schemas import TraceEntityType, TraceListResponse, TraceRecord

logger = logging.getLogger(__name__)

VIEWER_ROLES: tuple[BrandRole, ...] = (
    BrandRole.CREATOR,
    BrandRole.CONTENT_REVIEWER,
    BrandRole.VISUAL_REVIEWER,
)


def langfuse_configured(settings: Settings) -> bool:
    """Explicit 'tracing backend present' state; never exposes configuration values."""
    return bool(
        settings.langfuse_public_key and settings.langfuse_secret_key and settings.langfuse_host
    )


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status_code=422, detail=detail)


async def list_traces(
    session: Session,
    user: AuthenticatedUser,
    repository: TraceRecordRepository,
    settings: Settings,
    *,
    brand_id: UUID | None = None,
    entity_type: TraceEntityType | None = None,
    entity_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 20,
    offset: int = 0,
) -> TraceListResponse:
    start = time.perf_counter()
    if brand_id is not None:
        # 403 before any trace lookup: membership is resolved server-side only.
        authorize_brand_action(get_membership(session, user.id, brand_id), VIEWER_ROLES)
        authorized: tuple[UUID, ...] = (brand_id,)
    else:
        # No explicit brand: aggregate every brand the user is a member of
        # (zero memberships -> empty authorized set -> empty page, not an error).
        authorized = tuple(membership.brand_id for membership in list_memberships(session, user.id))
    if entity_id is not None and entity_type is None:
        raise _invalid("entity_id requires entity_type")
    if date_from is not None and date_to is not None and date_from > date_to:
        raise _invalid("from must not be after to")
    page = await repository.list(
        TraceQuery(
            brand_ids=tuple(str(brand) for brand in authorized),
            entity_type=entity_type.value if entity_type is not None else None,
            entity_id=str(entity_id) if entity_id is not None else None,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
    )
    logger.info(
        "trace.facade.list outcome=ok brands=%d items=%d total=%d latency_ms=%.1f",
        len(authorized),
        len(page.items),
        page.total,
        (time.perf_counter() - start) * 1000.0,
    )
    return TraceListResponse(
        items=list(page.items),
        total=page.total,
        langfuse_configured=langfuse_configured(settings),
    )


async def get_trace(
    session: Session,
    user: AuthenticatedUser,
    repository: TraceRecordRepository,
    trace_id: str,
) -> TraceRecord:
    start = time.perf_counter()
    authorized = tuple(
        membership.brand_id for membership in list_memberships(session, user.id)
    )
    record = await repository.get_by_trace_id(trace_id)
    # 404 for missing, unbound or foreign-brand traces alike: cross-brand
    # existence is never revealed.
    if record is None or record.brand_id is None or record.brand_id not in authorized:
        logger.info("trace.facade.get outcome=not_found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found")
    logger.info(
        "trace.facade.get outcome=ok latency_ms=%.1f",
        (time.perf_counter() - start) * 1000.0,
    )
    return record
