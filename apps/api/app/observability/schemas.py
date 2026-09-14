"""API schemas for the observability facade (change 009).

Response models expose ONLY the allowlisted scalar metadata: capability or
operation, prompt version, model, entity reference, brand, duration, outcome
(sanitized error type) and timestamps. Never secrets, raw prompts, responses,
chain-of-thought or provider payloads — by construction, there is no free-text
field to leak.
"""

import enum
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TraceEntityType(enum.StrEnum):
    """Allowlisted entity bindings for trace rows (spec 07 + design 009)."""

    BRAND_DNA_VERSION = "brand_dna_version"
    CREATIVE_VERSION = "creative_version"
    VISUAL_AUDIT = "visual_audit"


class TraceRecord(BaseModel):
    """One sanitized trace row (allowlist; no summary/payload fields exist)."""

    model_config = ConfigDict(extra="forbid")

    trace_id: str | None
    brand_id: uuid.UUID | None
    entity_type: TraceEntityType
    entity_id: uuid.UUID | None
    operation: str | None
    prompt_version: str | None
    model: str | None
    latency_ms: float | None
    outcome: str
    error_type: str | None
    created_at: datetime


class TraceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[TraceRecord]
    total: int
    langfuse_configured: bool
