"""Schemas for the creative module: strict inputs and API resources (API.md).

Human-edited output reuses the AI Platform `CreativeOutput` contract
(AI_SYSTEM.md) so AI-generated and human versions persist the same shape;
generate/regenerate land in phase 2 with the same contract.
"""

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.ai.contracts import CreativeOutput, RuleRef
from app.creative.models import (
    CreativeItemType,
    CreativeVersionOrigin,
    CreativeWorkflowStatus,
)

MAX_BRIEF_BYTES = 16 * 1024

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VersionEditOutput(CreativeOutput):
    """CreativeOutput for human edits: no retrieval, so applied rules default to none."""

    applied_rule_ids: list[RuleRef] = Field(default_factory=list, max_length=50)


def _require_brief_size(brief: dict[str, Any] | None) -> None:
    if brief is not None and len(str(brief).encode("utf-8")) > MAX_BRIEF_BYTES:
        raise ValueError(f"brief exceeds {MAX_BRIEF_BYTES} bytes serialized")


class ItemCreateIn(_Strict):
    brand_id: uuid.UUID
    type: CreativeItemType
    title: Title
    brief: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _brief_size(self) -> "ItemCreateIn":
        _require_brief_size(self.brief)
        return self


class VersionCreateIn(_Strict):
    brief: dict[str, Any] | None = None
    output: VersionEditOutput

    @model_validator(mode="after")
    def _brief_size(self) -> "VersionCreateIn":
        _require_brief_size(self.brief)
        return self


class SubmitIn(_Strict):
    version_id: uuid.UUID


class ItemSummary(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    type: CreativeItemType
    title: str
    workflow_status: CreativeWorkflowStatus
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    latest_version: int


class VersionSummary(BaseModel):
    id: uuid.UUID
    creative_item_id: uuid.UUID
    version: int
    origin: CreativeVersionOrigin
    brand_dna_version_id: uuid.UUID | None
    consistency_score: float | None
    created_by: uuid.UUID
    created_at: datetime


class VersionOut(VersionSummary):
    brief: dict[str, Any]
    output: CreativeOutput | None
    applied_rule_ids: list[str]
    consistency_result: dict[str, Any] | None
    langfuse_trace_id: str | None


class ItemOut(ItemSummary):
    current_version: VersionOut | None


class ItemList(BaseModel):
    items: list[ItemSummary]


class VersionList(BaseModel):
    versions: list[VersionSummary]


class AppliedContextOut(BaseModel):
    """Applied context of a version: the exact Brand DNA version and rules used."""

    creative_item_id: uuid.UUID
    version_id: uuid.UUID
    version: int
    brand_dna_version_id: uuid.UUID | None
    applied_rule_ids: list[str]
