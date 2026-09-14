"""Scoring helper (AI_SYSTEM.md): backend-computed, no automatic threshold."""

from app.ai.contracts import Check, ConsistencyResult, Finding
from app.ai.scoring import consistency_score


def check(check_id: str, status_: str) -> Check:
    return Check(check_id=check_id, label=f"Check {check_id}", status=status_)


def finding(rule_id: str, severity: str, status_: str) -> Finding:
    return Finding(
        rule_id=rule_id,
        category="tone",
        expected="Warm",
        detected="Cold",
        evidence="First sentence reads cold.",
        recommendation="Rewrite the opening in a warm register.",
        severity=severity,
        status=status_,
    )


def result(*findings: Finding, checks: list[Check] | None = None) -> ConsistencyResult:
    return ConsistencyResult(
        checks=checks or [check("c1", "pass")], findings=list(findings), summary="Resumen."
    )


def test_clean_run_scores_100() -> None:
    assert consistency_score(result()) == 100.0


def test_failed_findings_subtract_severity_weights() -> None:
    scored = result(
        finding("r-low", "low", "fail"),
        finding("r-med", "medium", "fail"),
        finding("r-high", "high", "fail"),
    )
    assert consistency_score(scored) == 61.0  # 100 - (4 + 10 + 25)


def test_passing_findings_never_penalize() -> None:
    scored = result(
        finding("r-low", "low", "pass"),
        finding("r-high", "high", "pass"),
    )
    assert consistency_score(scored) == 100.0


def test_score_floors_at_zero() -> None:
    scored = result(
        finding("r1", "high", "fail"),
        finding("r2", "high", "fail"),
        finding("r3", "high", "fail"),
        finding("r4", "high", "fail"),
        finding("r5", "high", "fail"),
    )
    assert consistency_score(scored) == 0.0
