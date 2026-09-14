"""ORM model for the observability trace read model (change 009).

One sanitized, allowlisted row per recorded span — scalar metadata only, never
raw prompts, responses, tokens or secrets. This index is derived data for the
facade; Langfuse remains the deep telemetry store. Rows without a `brand_id`
binding exist but are never servable (no authorization path).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TraceOutcome(enum.StrEnum):
    OK = "ok"
    ERROR = "error"


class TraceIndexEntry(Base):
    __tablename__ = "observability_trace_index"
    __table_args__ = (
        Index(
            "ix_observability_trace_index_brand_created",
            "brand_id",
            text("created_at DESC"),
        ),
        Index(
            "ix_observability_trace_index_entity",
            "entity_type",
            "entity_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    trace_id: Mapped[str | None] = mapped_column(String())
    brand_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("brands.id"))
    entity_type: Mapped[str] = mapped_column(String())
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    operation: Mapped[str | None] = mapped_column(String())
    prompt_version: Mapped[str | None] = mapped_column(String())
    model: Mapped[str | None] = mapped_column(String())
    latency_ms: Mapped[float | None] = mapped_column(Float())
    outcome: Mapped[TraceOutcome] = mapped_column(
        # Persist the enum *values* ("ok"/"error"): the PostgreSQL type created by
        # migration a3d8f2c6e9b1 only accepts those, while SQLAlchemy's default
        # would send the member names ("OK"/"ERROR") and fail with DataError.
        Enum(TraceOutcome, name="trace_outcome", values_callable=lambda e: [m.value for m in e])
    )
    error_type: Mapped[str | None] = mapped_column(String())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
