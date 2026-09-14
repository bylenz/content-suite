"""Visual audit policies (008 task 4.2): deterministic score, role gates and
the HIGH-exception rule."""

import uuid
from typing import Literal

import pytest
from fastapi import HTTPException

from app.ai.contracts import Finding
from app.creative.models import CreativeWorkflowStatus
from app.identity.models import BrandRole
from app.identity.policies import PermissionDeniedError
from app.visual_audit import policies


def _finding(
    severity: Literal["low", "medium", "high"],
    status: Literal["pass", "fail"],
    rule_id: str = "r1",
) -> Finding:
    return Finding(
        rule_id=rule_id,
        category="logo_usage",
        expected="x",
        detected="y",
        evidence="z",
        recommendation="fix it",
        severity=severity,
        status=status,
    )


def test_compute_score_is_100_with_no_fail_findings() -> None:
    findings = [_finding("high", "pass"), _finding("low", "pass")]
    assert policies.compute_score(findings) == 100.0


def test_compute_score_applies_the_documented_penalties() -> None:
    findings = [_finding("high", "fail"), _finding("medium", "fail"), _finding("low", "fail")]
    assert policies.compute_score(findings) == 100.0 - 25 - 10 - 3


def test_compute_score_floors_at_zero() -> None:
    findings = [_finding("high", "fail") for _ in range(10)]
    assert policies.compute_score(findings) == 0.0


def test_compute_score_is_deterministic_across_runs() -> None:
    findings = [_finding("high", "fail"), _finding("medium", "pass"), _finding("low", "fail")]
    first = policies.compute_score(findings)
    second = policies.compute_score(list(reversed(findings)))
    assert first == second == 100.0 - 25 - 3


def test_high_fail_findings_filters_correctly() -> None:
    findings = [
        _finding("high", "fail", "r1"),
        _finding("high", "pass", "r2"),
        _finding("medium", "fail", "r3"),
    ]
    high = policies.high_fail_findings(findings)
    assert [f.rule_id for f in high] == ["r1"]


def test_require_exception_for_high_findings_passes_without_high_fails() -> None:
    findings = [_finding("medium", "fail"), _finding("low", "fail")]
    policies.require_exception_for_high_findings(findings, exception_accepted=False)


def test_require_exception_for_high_findings_rejects_without_flag() -> None:
    findings = [_finding("high", "fail")]
    with pytest.raises(HTTPException) as exc_info:
        policies.require_exception_for_high_findings(findings, exception_accepted=False)
    assert exc_info.value.status_code == 422


def test_require_exception_for_high_findings_accepts_with_flag() -> None:
    findings = [_finding("high", "fail")]
    policies.require_exception_for_high_findings(findings, exception_accepted=True)


def test_require_uploadable_state_accepts_content_approved_and_changes_requested() -> None:
    item_id = uuid.uuid4()
    policies.require_uploadable_state(CreativeWorkflowStatus.CONTENT_APPROVED, item_id)
    policies.require_uploadable_state(CreativeWorkflowStatus.VISUAL_CHANGES_REQUESTED, item_id)


def test_require_uploadable_state_rejects_other_states() -> None:
    item_id = uuid.uuid4()
    for bad_status in (
        CreativeWorkflowStatus.DRAFT,
        CreativeWorkflowStatus.PENDING_CONTENT_REVIEW,
        CreativeWorkflowStatus.PENDING_VISUAL_REVIEW,
        CreativeWorkflowStatus.FINAL_APPROVED,
    ):
        with pytest.raises(policies.InvalidWorkflowTransitionError):
            policies.require_uploadable_state(bad_status, item_id)


class _Membership:
    def __init__(self, role: BrandRole) -> None:
        self.role = role


def test_require_uploader_only_allows_creator() -> None:
    policies.require_uploader(_Membership(BrandRole.CREATOR))
    for role in (BrandRole.CONTENT_REVIEWER, BrandRole.VISUAL_REVIEWER):
        with pytest.raises(PermissionDeniedError):
            policies.require_uploader(_Membership(role))


def test_require_reviewer_only_allows_visual_reviewer() -> None:
    policies.require_reviewer(_Membership(BrandRole.VISUAL_REVIEWER))
    for role in (BrandRole.CREATOR, BrandRole.CONTENT_REVIEWER):
        with pytest.raises(PermissionDeniedError):
            policies.require_reviewer(_Membership(role))


def test_require_audit_trigger_allows_creator_and_visual_reviewer_only() -> None:
    policies.require_audit_trigger(_Membership(BrandRole.CREATOR))
    policies.require_audit_trigger(_Membership(BrandRole.VISUAL_REVIEWER))
    with pytest.raises(PermissionDeniedError):
        policies.require_audit_trigger(_Membership(BrandRole.CONTENT_REVIEWER))


def test_require_reader_allows_all_three_roles() -> None:
    for role in (BrandRole.CREATOR, BrandRole.CONTENT_REVIEWER, BrandRole.VISUAL_REVIEWER):
        policies.require_reader(_Membership(role))


def test_require_reader_rejects_missing_membership() -> None:
    with pytest.raises(PermissionDeniedError):
        policies.require_reader(None)
