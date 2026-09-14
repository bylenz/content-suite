"""API schemas for the Recent Activity feed (change 014).

`ActivityEventOut` is a read-model union of two sources, never a new table:
a real `workflow_events` row, or one synthetic event derived per published
Brand DNA version. `source` tells the client which one it is; the unused
identity field for the other source is always null (never fabricated).
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ActivitySource(enum.StrEnum):
    """The two sources this change is scoped to (design.md Non-Goals: no more)."""

    WORKFLOW_EVENT = "WORKFLOW_EVENT"
    BRAND_DNA_PUBLISHED = "BRAND_DNA_PUBLISHED"


class ActivityEventOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    source: ActivitySource
    event_type: str
    actor_id: uuid.UUID | None
    created_at: datetime
    creative_item_id: uuid.UUID | None = None
    brand_dna_version_id: uuid.UUID | None = None
    metadata: dict[str, Any] | None = None


class ActivityListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ActivityEventOut]
    total: int
