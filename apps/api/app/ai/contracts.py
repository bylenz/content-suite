"""Structured output contracts for AI capabilities (AI_SYSTEM.md).

Pydantic v2 with extra="forbid": outputs missing a required field, with a wrong
type, an out-of-enum value, an unknown field or a broken content/sections
exclusivity are rejected — never passed through. `TraceSummary` is the bounded
allowlist that may travel in tracing spans (no free-text fields by design).
"""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


RuleRef = Annotated[str, Field(min_length=1, max_length=100)]


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
    output: CreativeOutput | ConsistencyResult | VisualAuditResult,
) -> TraceSummary:
    """Derive the bounded span summary from a validated output."""
    if isinstance(output, CreativeOutput):
        return TraceSummary(
            contract="CreativeOutput", ok=True, content_type=output.content_type,
            check_count=0, finding_count=0,
        )
    if isinstance(output, ConsistencyResult):
        return TraceSummary(
            contract="ConsistencyResult", ok=True,
            check_count=len(output.checks), finding_count=len(output.findings),
        )
    return TraceSummary(
        contract="VisualAuditResult", ok=True,
        check_count=len(output.checks), finding_count=len(output.findings),
    )
