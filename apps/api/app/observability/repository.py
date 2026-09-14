"""SQL implementation of `TraceRecordRepository`.

Sessions: the repository owns short-lived sessions from an injectable factory
(default: bound to the app engine). Writes commit independently of the domain
transaction that emitted the span, so error spans survive domain rollbacks and
never extend the caller's transaction. `save` is the only writer; reads narrow
strictly within the pre-authorized `brand_ids` carried by `TraceQuery`.

Rows without a `brand_id` binding are stored but are unreachable through this
repository: both read paths require a non-empty authorized brand set.
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_engine
from app.observability.models import TraceIndexEntry, TraceOutcome
from app.observability.ports import CapabilitySpan, TracePage, TraceQuery
from app.observability.schemas import TraceRecord

SessionFactory = Callable[[], Session]


def default_session_factory() -> SessionFactory:
    return sessionmaker(bind=get_engine())


def _authorized(query: TraceQuery) -> Select[tuple[TraceIndexEntry]]:
    """Base statement for servable rows: bound to a brand, inside the authorized set."""
    return select(TraceIndexEntry).where(
        TraceIndexEntry.brand_id.is_not(None),
        TraceIndexEntry.brand_id.in_(tuple(uuid.UUID(b) for b in query.brand_ids)),
    )


def _filtered(query: TraceQuery) -> Select[tuple[TraceIndexEntry]]:
    stmt = _authorized(query)
    if query.entity_type is not None:
        stmt = stmt.where(TraceIndexEntry.entity_type == query.entity_type)
        if query.entity_id is not None:
            stmt = stmt.where(TraceIndexEntry.entity_id == uuid.UUID(query.entity_id))
    if query.date_from is not None:
        stmt = stmt.where(TraceIndexEntry.created_at >= query.date_from)
    if query.date_to is not None:
        stmt = stmt.where(TraceIndexEntry.created_at <= query.date_to)
    return stmt


def _record(row: TraceIndexEntry) -> TraceRecord:
    """Map one ORM row to the allowlisted response contract (scalars only)."""
    return TraceRecord(
        trace_id=row.trace_id,
        brand_id=row.brand_id,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        operation=row.operation,
        prompt_version=row.prompt_version,
        model=row.model,
        latency_ms=row.latency_ms,
        outcome=row.outcome.value,
        error_type=row.error_type,
        created_at=row.created_at,
    )


class SqlTraceRecordRepository:
    def __init__(self, session_factory: SessionFactory | None = None) -> None:
        self._session_factory = session_factory or default_session_factory()

    async def save(self, span: CapabilitySpan, trace_id: str | None) -> None:
        entry = TraceIndexEntry(
            id=uuid.uuid4(),
            trace_id=trace_id,
            brand_id=uuid.UUID(span.brand_id) if span.brand_id is not None else None,
            entity_type=span.entity_type,
            entity_id=uuid.UUID(span.entity_id) if span.entity_id is not None else None,
            operation=span.operation,
            prompt_version=span.prompt_version,
            model=span.model,
            latency_ms=span.latency_ms,
            outcome=TraceOutcome.ERROR if span.error is not None else TraceOutcome.OK,
            error_type=span.error,
            # Explicit aware timestamp: keeps the SQLite dev/test seam comparable
            # with the aware ISO query params (server_default stays as DB default).
            created_at=datetime.now(UTC),
        )
        with self._session_factory() as session:
            session.add(entry)
            session.commit()

    async def list(self, query: TraceQuery) -> TracePage:
        if not query.brand_ids:
            return TracePage(items=(), total=0)
        with self._session_factory() as session:
            total = session.scalar(select(func.count()).select_from(_filtered(query).subquery()))
            rows = list(
                session.scalars(
                    _filtered(query).order_by(TraceIndexEntry.created_at.desc()).limit(
                        query.limit
                    ).offset(query.offset)
                )
            )
        return TracePage(items=tuple(_record(row) for row in rows), total=total or 0)

    async def get_by_trace_id(self, trace_id: str) -> TraceRecord | None:
        with self._session_factory() as session:
            row = session.scalars(
                select(TraceIndexEntry).where(TraceIndexEntry.trace_id == trace_id)
            ).first()
        return _record(row) if row is not None else None
