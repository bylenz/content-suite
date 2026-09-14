"""Structured output contracts for AI capabilities (AI_SYSTEM.md).

Pydantic v2 with extra="forbid": outputs missing a required field, with a wrong
type, an out-of-enum value, an unknown field or a broken content/sections
exclusivity are rejected — never passed through. `TraceSummary` is the bounded
allowlist that may travel in tracing spans (no free-text fields by design).
"""

from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_serializer,
    model_validator,
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


RuleRef = Annotated[str, Field(min_length=1, max_length=100)]

# --- Brand DNA document contract (change 013): moved here as-is from
# app/brand_dna/schemas.py so `run_capability` can validate generation output
# against the exact same contract manual authoring persists (design.md
# 013-brand-dna-generation). Fields, limits and validators are unchanged;
# `app/brand_dna/schemas.py` now imports these from this module.

MAX_DOCUMENT_BYTES = 32 * 1024

Narrative500 = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]
Narrative1000 = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]
Label60 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Example300 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


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


class _StrictOmitNone(_Strict):
    """Strict model whose serialization omits None values.

    Optional fields added by later changes (e.g. the Knowledge counts) stay
    absent from serialized summaries instead of adding null noise; dumps of
    fully-populated models are unchanged.
    """

    @model_serializer(mode="wrap")
    def _omit_none(self, handler) -> dict:
        return {key: value for key, value in handler(self).items() if value is not None}


class Finding(_Strict):
    """Shared finding across consistency and visual audits."""

    rule_id: RuleRef
    category: str = Field(min_length=1, max_length=50)
    expected: str = Field(min_length=1, max_length=500)
    detected: str = Field(min_length=1, max_length=500)
    evidence: str = Field(min_length=1, max_length=1000)
    recommendation: str = Field(min_length=1, max_length=1000)
    severity: Literal["low", "medium", "high"]
    status: Literal["pass", "fail"]


class Check(_Strict):
    check_id: RuleRef
    label: str = Field(min_length=1, max_length=200)
    status: Literal["pass", "fail"]


class CreativeSection(_Strict):
    heading: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=10000)


class CreativeOutput(_Strict):
    content_type: Literal["product_description", "video_script", "image_prompt"]
    title: str = Field(min_length=1, max_length=200)
    # Exactly one of content / structured_sections must be present (validator below).
    content: str | None = Field(default=None, min_length=1, max_length=10000)
    structured_sections: list[CreativeSection] | None = Field(default=None, max_length=50)
    applied_rule_ids: list[RuleRef] = Field(max_length=50)

    @classmethod
    def normalize_provider_payload(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Collapse provider quirks before validating a *model* payload.

        OpenAI strict json_schema mode forces every key to be present, so the
        model sometimes fills both bodies (e.g. a video script flattened into
        `content` next to its `structured_sections`) or sends `""` / `[]` for
        the body it did not use. Prefer `structured_sections` when both carry
        data and treat empty values as absent. Only the capability runner calls
        this: human edits through the API keep the strict exactly-one contract.
        """
        content = data.get("content")
        sections = data.get("structured_sections")
        if content is not None and not str(content).strip():
            data = {**data, "content": None}
            content = None
        if sections is not None and len(sections) == 0:
            data = {**data, "structured_sections": None}
            sections = None
        if content is not None and sections is not None:
            data = {**data, "content": None}
        return data

    @model_validator(mode="after")
    def _exactly_one_body_and_unique_rules(self) -> Self:
        if (self.content is None) == (self.structured_sections is None):
            raise ValueError("exactly one of content or structured_sections must be present")
        if len(set(self.applied_rule_ids)) != len(self.applied_rule_ids):
            raise ValueError("applied_rule_ids must not contain duplicates")
        return self


class ConsistencyResult(_Strict):
    checks: list[Check] = Field(max_length=100)
    findings: list[Finding] = Field(max_length=100)
    summary: str = Field(min_length=1, max_length=2000)


class VisualAuditResult(_Strict):
    checks: list[Check] = Field(max_length=100)
    findings: list[Finding] = Field(max_length=100)
    summary: str = Field(min_length=1, max_length=2000)


class TraceSummary(_StrictOmitNone):
    """Allowlisted, scalar-only span summary: cannot carry raw payloads by design."""

    contract: Literal[
        "CreativeOutput",
        "ConsistencyResult",
        "VisualAuditResult",
        "BrandDnaDocument",
        "KnowledgeSync",
        "KnowledgeEmbed",
        "KnowledgeRetrieval",
    ]
    ok: bool
    content_type: Literal["product_description", "video_script", "image_prompt"] | None = None
    check_count: int = Field(default=0, ge=0, le=100)
    finding_count: int = Field(default=0, ge=0, le=100)
    # Knowledge counts: only valid for the Knowledge* contracts (validator below).
    chunk_count: int | None = Field(default=None, ge=0, le=10000)
    mandatory_count: int | None = Field(default=None, ge=0, le=10000)
    semantic_count: int | None = Field(default=None, ge=0, le=10000)

    @model_validator(mode="after")
    def _content_type_only_for_creative(self) -> Self:
        if self.contract == "CreativeOutput" and self.content_type is None:
            raise ValueError("content_type is required when contract is CreativeOutput")
        if self.contract != "CreativeOutput" and self.content_type is not None:
            raise ValueError("content_type is only allowed when contract is CreativeOutput")
        return self

    @model_validator(mode="after")
    def _knowledge_counts_only_for_knowledge_contracts(self) -> Self:
        is_knowledge = self.contract in ("KnowledgeSync", "KnowledgeEmbed", "KnowledgeRetrieval")
        knowledge_fields = {
            "chunk_count": self.chunk_count,
            "mandatory_count": self.mandatory_count,
            "semantic_count": self.semantic_count,
        }
        if not is_knowledge and any(value is not None for value in knowledge_fields.values()):
            raise ValueError("knowledge counts are only allowed for Knowledge contracts")
        if is_knowledge and (self.check_count != 0 or self.finding_count != 0):
            raise ValueError("Knowledge contracts leave check_count/finding_count at 0")
        return self


def build_trace_summary(
    output: CreativeOutput | ConsistencyResult | VisualAuditResult | BrandDnaDocument,
) -> TraceSummary:
    """Derive the bounded span summary from a validated output."""
    if isinstance(output, CreativeOutput):
        return TraceSummary(
            contract="CreativeOutput",
            ok=True,
            content_type=output.content_type,
            check_count=0,
            finding_count=0,
        )
    if isinstance(output, ConsistencyResult):
        return TraceSummary(
            contract="ConsistencyResult",
            ok=True,
            check_count=len(output.checks),
            finding_count=len(output.findings),
        )
    if isinstance(output, BrandDnaDocument):
        # No checks/findings apply to a generated document: the bounded floor (0/0).
        return TraceSummary(contract="BrandDnaDocument", ok=True, check_count=0, finding_count=0)
    return TraceSummary(
        contract="VisualAuditResult",
        ok=True,
        check_count=len(output.checks),
        finding_count=len(output.findings),
    )
