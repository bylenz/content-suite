"""Deterministic scoring helpers (AI_SYSTEM.md): the model classifies findings,
the backend computes the score. No automatic approval threshold exists.

Score formula (documented decision): 100 minus the severity-weighted penalty of
FAILED findings (low=4, medium=10, high=25), floored at 0 and rounded to 2
decimals. Passing findings never add score back: a clean run is 100 only when
no finding failed.
"""

from app.ai.contracts import ConsistencyResult

SEVERITY_WEIGHTS: dict[str, float] = {"low": 4.0, "medium": 10.0, "high": 25.0}


def consistency_score(result: ConsistencyResult) -> float:
    """Compute the numeric consistency score from failed finding severities."""
    penalty = sum(
        SEVERITY_WEIGHTS[finding.severity]
        for finding in result.findings
        if finding.status == "fail"
    )
    return round(max(0.0, 100.0 - penalty), 2)
