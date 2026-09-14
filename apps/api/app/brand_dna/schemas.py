"""Schemas for the brand_dna module: canonical document contract and API resources.

The canonical document contract is strict (extra="forbid"): every string is
trimmed before validation/persistence, empty-after-trim strings are invalid,
types/cardinalities/limits match design.md exactly, and unknown sections,
fields or keys are rejected with 422 and their field paths.
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.brand_dna.models import BrandDnaStatus, KnowledgeStatus

MAX_DOCUMENT_BYTES = 32 * 1024

Narrative500 = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]
Narrative1000 = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]
Label60 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Example300 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IdentitySection(_Strict):
    purpose: Narrative500
    positioning: Narrative500
    personality_traits: list[Label60] = Field(min_length=1, max_length=8)
    audience: Narrative500


class VoiceSection(_Strict):
    tone_characteristics: list[Label60] = Field(min_length=1, max_length=8)
    usage_guide: Narrative1000
    preferred_vocabulary: list[Label60] = Field(max_length=30)
    avoid_vocabulary: list[Label60] = Field(max_length=30)
    do_examples: list[Example300] = Field(min_length=1, max_length=10)
    dont_examples: list[Example300] = Field(min_length=1, max_length=10)


class MessagePillar(_Strict):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    description: Example300


class CommunicationSection(_Strict):
    message_pillars: list[MessagePillar] = Field(min_length=1, max_length=5)
    rules: list[Example300] = Field(min_length=1, max_length=20)


class VisualRulesSection(_Strict):
    visual_personality: Narrative500
    imagery_direction: Narrative500
    composition: Narrative500
    logo_usage: Narrative500


class RestrictionsSection(_Strict):
    rules: list[Example300] = Field(min_length=1, max_length=20)


class BrandDnaDocument(_Strict):
    identity: IdentitySection
    voice: VoiceSection
    communication: CommunicationSection
    visual_rules: VisualRulesSection
    restrictions: RestrictionsSection

    @model_validator(mode="after")
    def _serialized_size_limit(self) -> "BrandDnaDocument":
        if len(self.model_dump_json().encode("utf-8")) > MAX_DOCUMENT_BYTES:
            raise ValueError(f"document exceeds {MAX_DOCUMENT_BYTES} bytes serialized")
        return self


def derive_section_counts(document: BrandDnaDocument) -> dict[str, int]:
    """Deterministic per-section summary: one entry per atomic unit.

    A unit is a list item or a narrative/scalar field, so every section yields
    a stable count derived from the document itself (no denormalized counters):
    identity = 3 narratives + traits; voice = guide + its 5 lists;
    communication = pillars + rules; visual_rules = its 4 narratives;
    restrictions = rules.
    """
    return {
        "identity": 3 + len(document.identity.personality_traits),
        "voice": 1
        + len(document.voice.tone_characteristics)
        + len(document.voice.preferred_vocabulary)
        + len(document.voice.avoid_vocabulary)
        + len(document.voice.do_examples)
        + len(document.voice.dont_examples),
        "communication": len(document.communication.message_pillars)
        + len(document.communication.rules),
        "visual_rules": 4,
        "restrictions": len(document.restrictions.rules),
    }


class BrandDnaVersionOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    version: int
    status: BrandDnaStatus
    document: BrandDnaDocument
    created_by: uuid.UUID
    created_at: datetime
    published_at: datetime | None
    knowledge_status: KnowledgeStatus
    section_counts: dict[str, int]


class BrandDnaVersionSummary(BaseModel):
    """Version resource without the full document (history list entries)."""

    id: uuid.UUID
    brand_id: uuid.UUID
    version: int
    status: BrandDnaStatus
    created_by: uuid.UUID
    created_at: datetime
    published_at: datetime | None
    knowledge_status: KnowledgeStatus
    section_counts: dict[str, int]


class BrandDnaOverview(BaseModel):
    active: BrandDnaVersionOut | None
    draft: BrandDnaVersionOut | None


class BrandDnaVersionList(BaseModel):
    versions: list[BrandDnaVersionSummary]


class DraftUpdateIn(BaseModel):
    document: BrandDnaDocument


class PublishIn(BaseModel):
    expected_draft_id: uuid.UUID
