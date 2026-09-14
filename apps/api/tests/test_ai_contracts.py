"""Contracts (3.1): valid examples pass; malformed outputs are rejected."""

import pytest
from pydantic import ValidationError

from app.ai.contracts import (
    Check,
    ConsistencyResult,
    CreativeOutput,
    Finding,
    TraceSummary,
    VisualAuditResult,
    build_trace_summary,
)


def finding_payload(**overrides) -> dict:
    payload = {
        "rule_id": "rule-1",
        "category": "tone",
        "expected": "Warm and energetic",
        "detected": "Cold and formal",
        "evidence": "Opening line reads like a legal notice",
        "recommendation": "Rewrite the opening with a friendly greeting",
        "severity": "medium",
        "status": "fail",
    }
    payload.update(overrides)
    return payload


def check_payload(**overrides) -> dict:
    payload = {"check_id": "check-1", "label": "Tone matches brand", "status": "pass"}
    payload.update(overrides)
    return payload


def creative_payload(**overrides) -> dict:
    payload = {
        "content_type": "product_description",
        "title": "Quinoa Bites",
        "content": "Bites de quinua horneados con ingredientes reales.",
        "applied_rule_ids": ["rule-1", "rule-2"],
    }
    payload.update(overrides)
    return payload


def consistency_payload(**overrides) -> dict:
    payload = {
        "checks": [check_payload()],
        "findings": [finding_payload()],
        "summary": "El contenido cumple el tono de marca en general.",
    }
    payload.update(overrides)
    return payload


def test_valid_finding_and_check_are_accepted() -> None:
    finding = Finding.model_validate(finding_payload())
    assert finding.severity == "medium"
    check = Check.model_validate(check_payload())
    assert check.status == "pass"


@pytest.mark.parametrize(
    "overrides",
    [
        {"rule_id": ""},  # required min length
        {"rule_id": "x" * 101},  # over max length
        {"severity": "critical"},  # out of enum
        {"status": "maybe"},  # out of enum
        {"category": 42},  # wrong type
    ],
)
def test_malformed_finding_is_rejected(overrides) -> None:
    with pytest.raises(ValidationError):
        Finding.model_validate(finding_payload(**overrides))


def test_extra_field_is_rejected_by_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        Finding.model_validate(finding_payload(chain_of_thought="because..."))
    with pytest.raises(ValidationError):
        CreativeOutput.model_validate(creative_payload(scratch="internal notes"))


def test_valid_creative_output_accepts_content_and_sections_variants() -> None:
    by_content = CreativeOutput.model_validate(creative_payload())
    assert by_content.content is not None and by_content.structured_sections is None
    by_sections = CreativeOutput.model_validate(
        creative_payload(
            content=None,
            structured_sections=[{"heading": "Hook", "body": "Snack real, energia real."}],
        )
    )
    assert by_sections.content is None
    assert by_sections.structured_sections is not None
    assert by_sections.structured_sections[0].heading == "Hook"


def test_creative_output_rejects_broken_body_exclusivity() -> None:
    both = creative_payload(structured_sections=[{"heading": "H", "body": "B"}])
    with pytest.raises(ValidationError):
        CreativeOutput.model_validate(both)  # content + sections at the same time
    neither = creative_payload(content=None)
    with pytest.raises(ValidationError):
        CreativeOutput.model_validate(neither)


def test_creative_output_rejects_bad_content_type_and_duplicate_rules() -> None:
    with pytest.raises(ValidationError):
        CreativeOutput.model_validate(creative_payload(content_type="podcast"))
    with pytest.raises(ValidationError):
        CreativeOutput.model_validate(creative_payload(applied_rule_ids=["rule-1", "rule-1"]))
    with pytest.raises(ValidationError):
        CreativeOutput.model_validate(
            creative_payload(applied_rule_ids=[f"rule-{i}" for i in range(51)])
        )


def test_creative_output_requires_applied_rule_ids() -> None:
    payload = creative_payload()
    payload.pop("applied_rule_ids")
    with pytest.raises(ValidationError):
        CreativeOutput.model_validate(payload)  # required field: no default


def test_valid_consistency_and_visual_audit_results() -> None:
    consistency = ConsistencyResult.model_validate(consistency_payload())
    assert len(consistency.checks) == 1
    audit = VisualAuditResult.model_validate(consistency_payload(summary="Visual conforme."))
    assert audit.findings[0].rule_id == "rule-1"


def test_results_reject_missing_and_malformed_fields() -> None:
    with pytest.raises(ValidationError):
        ConsistencyResult.model_validate(consistency_payload(checks="not-a-list"))
    with pytest.raises(ValidationError):
        VisualAuditResult.model_validate(consistency_payload(summary=""))
    with pytest.raises(ValidationError):
        payload = consistency_payload(checks=[], findings=[], summary="ok")
        ConsistencyResult.model_validate(payload | {"extra": 1})


def test_trace_summary_enforces_allowlist_and_content_type_rules() -> None:
    creative = TraceSummary(
        contract="CreativeOutput", ok=True, content_type="video_script",
        check_count=0, finding_count=0,
    )
    assert creative.ok
    with pytest.raises(ValidationError):
        TraceSummary(contract="CreativeOutput", ok=True, check_count=0, finding_count=0)
    with pytest.raises(ValidationError):
        TraceSummary(
            contract="ConsistencyResult", ok=True, content_type="video_script",
            check_count=1, finding_count=1,
        )
    with pytest.raises(ValidationError):
        TraceSummary(contract="ConsistencyResult", ok=True, check_count=101, finding_count=0)
    with pytest.raises(ValidationError):
        TraceSummary.model_validate(
            {
                "contract": "ConsistencyResult", "ok": True, "check_count": 1,
                "finding_count": 1, "note": "free text",
            }
        )


def test_build_trace_summary_derives_counts_per_contract() -> None:
    creative_summary = build_trace_summary(CreativeOutput.model_validate(creative_payload()))
    assert creative_summary.model_dump() == {
        "contract": "CreativeOutput", "ok": True, "content_type": "product_description",
        "check_count": 0, "finding_count": 0,
    }
    consistency_summary = build_trace_summary(
        ConsistencyResult.model_validate(
            consistency_payload(checks=[check_payload(), check_payload(check_id="check-2")])
        )
    )
    assert consistency_summary.check_count == 2
    assert consistency_summary.finding_count == 1
    audit_summary = build_trace_summary(VisualAuditResult.model_validate(consistency_payload()))
    assert audit_summary.contract == "VisualAuditResult"
    assert audit_summary.content_type is None
