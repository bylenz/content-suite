"""Schemas for visual_audit: strict inputs and API resources (API.md).

The Vision findings/checks contract deliberately reuses the existing shared
`app.ai.contracts` `Finding`/`Check` (severity `low|medium|high`, status
`pass|fail`, `extra="forbid"`) that `ConsistencyResult`/`VisualAuditResult`
already ship with and that `app.ai.runner.run_capability` is typed against
(005/AI Platform, already implemented and tested). Introducing a second,
differently-cased contract per design.md D6's literal wording
(`severity: HIGH|MEDIUM|LOW`, `status: PASS|FAIL`) would either fork the
already-shipped AI platform contract -- breaking the untouchable
`test_ai_*`/`test_creative_ai` suites, which assert the lowercase shape -- or
duplicate an equivalent contract for no behavioral gain. This module reuses
the established one; severity/status literals are lowercase everywhere in
visual_audit as a result (documented deviation, see final report).
"""

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.ai.contracts import Check, Finding
from app.creative.schemas import ItemSummary
from app.visual_audit.models import VisualReviewDecision


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


Feedback = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class ApproveIn(_Strict):
    exception_accepted: bool = False


class RequestChangesIn(_Strict):
    feedback: Feedback


class VisualAssetOut(BaseModel):
    """Never exposes `storage_path` (D4): `signed_url` is computed at the router boundary."""

    id: uuid.UUID
    creative_item_id: uuid.UUID
    version: int
    signed_url: str
    metadata: dict[str, Any]
    uploaded_by: uuid.UUID
    created_at: datetime


class VisualAssetList(BaseModel):
    assets: list[VisualAssetOut]


class VisualAuditOut(BaseModel):
    id: uuid.UUID
    visual_asset_id: uuid.UUID
    brand_dna_version_id: uuid.UUID
    checks: list[Check]
    findings: list[Finding]
    score: float
    summary: str
    applied_context: dict[str, Any]
    langfuse_trace_id: str | None
    created_at: datetime


class VisualReviewOut(BaseModel):
    id: uuid.UUID
    visual_audit_id: uuid.UUID
    reviewer_id: uuid.UUID
    decision: VisualReviewDecision
    feedback: str | None
    exception_accepted: bool
    evidence: dict[str, Any] | None
    created_at: datetime


class QueueItemOut(BaseModel):
    item: ItemSummary
    asset: VisualAssetOut
    latest_audit: VisualAuditOut | None


class QueueOut(BaseModel):
    items: list[QueueItemOut]


class DecisionOut(BaseModel):
    """Response for approve/request-changes: the item's new state + the decision."""

    item: ItemSummary
    review: VisualReviewOut


class VisualHistoryEntryOut(BaseModel):
    asset: VisualAssetOut
    audits: list[VisualAuditOut]
    reviews: list[VisualReviewOut]


class VisualAuditHistoryOut(BaseModel):
    item: ItemSummary
    entries: list[VisualHistoryEntryOut]
