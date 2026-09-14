"""Observability facade router. No SQL here; auth dependency, membership-first
service and the repository port resolve everything (design 009).

Unknown query parameters are ignored (FastAPI default) — the allowlist is
exactly what is declared below. Errors flow through the central envelope:
403 without membership, 404 for missing/foreign traces, 422 for invalid
parameter combinations.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session
from app.identity.auth import AuthenticatedUser, get_current_user
from app.observability import service
from app.observability.ports import TraceRecordRepository
from app.observability.repository import SqlTraceRecordRepository
from app.observability.schemas import TraceEntityType, TraceListResponse, TraceRecord

router = APIRouter(prefix="/traces", tags=["observability"])


def get_trace_repository() -> TraceRecordRepository:
    """Compositional root for the read model (overridable with a fake in tests)."""
    return SqlTraceRecordRepository()


@router.get("", response_model=TraceListResponse)
async def list_traces(
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    repository: TraceRecordRepository = Depends(get_trace_repository),
    settings: Settings = Depends(get_settings),
    brand_id: UUID | None = Query(default=None),
    entity_type: TraceEntityType | None = Query(default=None),
    entity_id: UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> TraceListResponse:
    return await service.list_traces(
        session,
        user,
        repository,
        settings,
        brand_id=brand_id,
        entity_type=entity_type,
        entity_id=entity_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


@router.get("/{trace_id}", response_model=TraceRecord)
async def get_trace(
    trace_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    repository: TraceRecordRepository = Depends(get_trace_repository),
) -> TraceRecord:
    return await service.get_trace(session, user, repository, trace_id)
