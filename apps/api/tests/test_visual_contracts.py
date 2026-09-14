"""Visual audit contracts (008 task 4.1): findings contract, response schemas
never expose `storage_path` and always serialize a `signed_url`.

The Vision findings contract is the existing shared `app.ai.contracts.Finding`
(reused by design -- see `app/visual_audit/schemas.py`'s module docstring for
why a second, differently-cased contract was not introduced)."""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.ai.contracts import Finding
from app.visual_audit.models import VisualReviewDecision
from app.visual_audit.schemas import DecisionOut, VisualAssetOut, VisualAuditOut


def _finding(**overrides) -> dict:
    base = {
        "rule_id": "rule-logo-1",
        "category": "logo_usage",
        "expected": "Logo top-left with clear space",
        "detected": "Logo centered with no clear space",
        "evidence": "Logo appears centered in the frame",
        "recommendation": "Move the logo to the top-left corner",
        "severity": "high",
        "status": "fail",
    }
    base.update(overrides)
    return base


def test_finding_accepts_a_well_formed_payload() -> None:
    finding = Finding.model_validate(_finding())
    assert finding.severity == "high"
    assert finding.status == "fail"


def test_finding_rejects_missing_field() -> None:
    payload = _finding()
    del payload["evidence"]
    with pytest.raises(ValidationError):
        Finding.model_validate(payload)


def test_finding_rejects_out_of_enum_severity() -> None:
    with pytest.raises(ValidationError):
        Finding.model_validate(_finding(severity="critical"))


def test_finding_rejects_out_of_enum_status() -> None:
    with pytest.raises(ValidationError):
        Finding.model_validate(_finding(status="warn"))


def test_finding_rejects_unknown_extra_field() -> None:
    with pytest.raises(ValidationError):
        Finding.model_validate(_finding(unexpected_field="nope"))


def test_visual_asset_out_never_has_a_storage_path_field() -> None:
    """Response schema shape check (D4): no `storage_path` field exists at all."""
    assert "storage_path" not in VisualAssetOut.model_fields
    assert "signed_url" in VisualAssetOut.model_fields


def test_visual_asset_out_serializes_signed_url_not_a_path() -> None:
    asset = VisualAssetOut(
        id=uuid.uuid4(),
        creative_item_id=uuid.uuid4(),
        version=1,
        signed_url="https://signed.example/object?token=abc",
        metadata={"content_type": "image/png"},
        uploaded_by=uuid.uuid4(),
        created_at=datetime.now(UTC),
    )
    dumped = asset.model_dump(mode="json")
    assert dumped["signed_url"] == "https://signed.example/object?token=abc"
    assert "storage_path" not in dumped


def test_visual_audit_out_serializes_findings_and_checks() -> None:
    audit = VisualAuditOut(
        id=uuid.uuid4(),
        visual_asset_id=uuid.uuid4(),
        brand_dna_version_id=uuid.uuid4(),
        checks=[{"check_id": "check-logo", "label": "Logo usage", "status": "pass"}],
        findings=[_finding()],
        score=75.0,
        summary="One HIGH finding on logo placement.",
        applied_context={"mandatory_rule_count": 3, "semantic_rule_count": 5},
        langfuse_trace_id=None,
        created_at=datetime.now(UTC),
    )
    dumped = audit.model_dump(mode="json")
    assert dumped["findings"][0]["severity"] == "high"
    assert dumped["score"] == 75.0


def test_decision_out_reuses_item_summary_and_review_shape() -> None:
    assert "item" in DecisionOut.model_fields
    assert "review" in DecisionOut.model_fields
    assert VisualReviewDecision.APPROVED.value == "APPROVED"
    assert VisualReviewDecision.CHANGES_REQUESTED.value == "CHANGES_REQUESTED"
