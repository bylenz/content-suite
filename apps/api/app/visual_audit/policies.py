"""Domain policies for visual_audit: role gates, workflow guards and the
deterministic score function (design D5/D7).
"""

import uuid
from collections.abc import Sequence

from fastapi import HTTPException, status

from app.ai.contracts import Finding
from app.creative.models import CreativeWorkflowStatus
from app.identity.models import BrandRole
from app.identity.policies import authorize_brand_action

# Any brand member may read visual assets/audits/history for their brand.
READER_ROLES = (BrandRole.CREATOR, BrandRole.CONTENT_REVIEWER, BrandRole.VISUAL_REVIEWER)
# Only the Creator uploads a visual.
UPLOAD_ROLES = (BrandRole.CREATOR,)
# Either the Creator (pre-check before submitting to the queue) or the Visual
# Reviewer (working the queue) may trigger an audit run.
AUDIT_TRIGGER_ROLES = (BrandRole.CREATOR, BrandRole.VISUAL_REVIEWER)
# Only the Visual Reviewer's queue and decisions.
QUEUE_ROLES = (BrandRole.VISUAL_REVIEWER,)
DECISION_ROLES = (BrandRole.VISUAL_REVIEWER,)

# Items reachable for a new visual upload (design/spec: first upload from
# CONTENT_APPROVED, corrections from VISUAL_CHANGES_REQUESTED).
UPLOADABLE_STATUSES = frozenset(
    {CreativeWorkflowStatus.CONTENT_APPROVED, CreativeWorkflowStatus.VISUAL_CHANGES_REQUESTED}
)

# Score weights (design D5): deterministic, no randomness, no model dependency.
_SEVERITY_PENALTY = {"high": 25, "medium": 10, "low": 3}


class InvalidWorkflowTransitionError(Exception):
    """Raised when a visual upload/decision precondition is not satisfiable."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        # Keep details JSON-serializable for the error envelope (uuid -> str, None stays None).
        self.details = {
            key: str(value) if isinstance(value, uuid.UUID) else value
            for key, value in (details or {}).items()
        }


def require_reader(membership) -> None:
    authorize_brand_action(membership, READER_ROLES)


def require_uploader(membership) -> None:
    """Only CREATOR members may upload a new visual version."""
    authorize_brand_action(membership, UPLOAD_ROLES)


def require_audit_trigger(membership) -> None:
    authorize_brand_action(membership, AUDIT_TRIGGER_ROLES)


def require_queue_reader(membership) -> None:
    authorize_brand_action(membership, QUEUE_ROLES)


def require_reviewer(membership) -> None:
    """Only VISUAL_REVIEWER members may approve or request changes."""
    authorize_brand_action(membership, DECISION_ROLES)


def require_uploadable_state(workflow_status: CreativeWorkflowStatus, item_id: uuid.UUID) -> None:
    if workflow_status not in UPLOADABLE_STATUSES:
        raise InvalidWorkflowTransitionError(
            "Creative item cannot receive a new visual from its current state",
            {"item_id": item_id, "workflow_status": workflow_status.value},
        )


def compute_score(findings: Sequence[Finding]) -> float:
    """Deterministic score (design D5): 100 minus the penalty of every FAIL
    finding by severity, floored at 0. Pure function: same findings always
    produce the same score, no model call, no randomness.
    """
    penalty = sum(
        _SEVERITY_PENALTY[finding.severity] for finding in findings if finding.status == "fail"
    )
    return float(max(0, 100 - penalty))


def high_fail_findings(findings: Sequence[Finding]) -> list[Finding]:
    return [f for f in findings if f.severity == "high" and f.status == "fail"]


def require_exception_for_high_findings(
    findings: Sequence[Finding], *, exception_accepted: bool
) -> None:
    """Approval with >=1 HIGH fail finding requires explicit `exception_accepted=true`
    (design D7); otherwise 422 -- no decision is created."""
    if high_fail_findings(findings) and not exception_accepted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Approval requires exception_accepted=true: this audit has "
                "unresolved HIGH severity findings"
            ),
        )
