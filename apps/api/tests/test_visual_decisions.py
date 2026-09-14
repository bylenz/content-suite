"""Visual review decisions (008 task 5.3): reviewer-only, HIGH exception rule,
approve/request-changes transitions + workflow events, idempotent retries."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.fakes import FakeEmbeddingModel, FakeVisionModel
from app.creative.models import CreativeItem, CreativeWorkflowStatus, WorkflowEvent
from app.identity.models import BrandRole
from app.visual_audit.models import VisualReview
from tests.conftest import auth_header, make_workspace, seed_synced_knowledge
from tests.test_visual_audit_service import FAIL_HIGH_PAYLOAD, run_audit
from tests.test_visual_upload import (
    clear_visual_adapter_overrides,
    install_visual_adapters,
    make_approved_item,
    upload_visual,
)


def approve(client: TestClient, token: str, audit_id, exception_accepted: bool | None = None):
    body = {} if exception_accepted is None else {"exception_accepted": exception_accepted}
    return client.post(
        f"/api/v1/visual-audits/{audit_id}/approve", headers=auth_header(token), json=body
    )


def request_changes(client: TestClient, token: str, audit_id, feedback: str = "Fix the logo"):
    return client.post(
        f"/api/v1/visual-audits/{audit_id}/request-changes",
        headers=auth_header(token),
        json={"feedback": feedback},
    )


def _setup_audited_asset(
    client: TestClient, session: Session, workspace: dict, *, vision_payload=None
):
    item = make_approved_item(client, session, workspace)
    storage, _tracer = install_visual_adapters()
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    upload = upload_visual(client, creator_token, item["id"])
    assert upload.status_code == 201
    asset_id = upload.json()["id"]

    seed_synced_knowledge(
        session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id
    )
    vision = (
        FakeVisionModel(structured_output=vision_payload) if vision_payload else FakeVisionModel()
    )
    install_visual_adapters(storage=storage, vision=vision, embedding=FakeEmbeddingModel())
    audit_response = run_audit(client, workspace["tokens"][BrandRole.VISUAL_REVIEWER], asset_id)
    assert audit_response.status_code == 200, audit_response.text
    return item, asset_id, audit_response.json()["id"]


def test_approve_without_high_findings_transitions_to_final_approved(
    client: TestClient, session: Session
):
    workspace = make_workspace(session)
    item, _asset_id, audit_id = _setup_audited_asset(client, session, workspace)
    try:
        response = approve(client, workspace["tokens"][BrandRole.VISUAL_REVIEWER], audit_id)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["item"]["workflow_status"] == "FINAL_APPROVED"
        assert body["review"]["decision"] == "APPROVED"
        assert body["review"]["exception_accepted"] is False
        assert body["review"]["evidence"] is None

        row = session.get(CreativeItem, uuid.UUID(str(item["id"])))
        assert row is not None
        assert row.workflow_status == CreativeWorkflowStatus.FINAL_APPROVED
        events = list(
            session.scalars(
                select(WorkflowEvent).where(
                    WorkflowEvent.creative_item_id == uuid.UUID(str(item["id"])),
                    WorkflowEvent.event_type == "FINAL_APPROVED",
                )
            )
        )
        assert len(events) == 1
    finally:
        clear_visual_adapter_overrides()


def test_approve_with_high_finding_without_exception_is_422(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item, _asset_id, audit_id = _setup_audited_asset(
        client, session, workspace, vision_payload=FAIL_HIGH_PAYLOAD
    )
    try:
        response = approve(client, workspace["tokens"][BrandRole.VISUAL_REVIEWER], audit_id)

        assert response.status_code == 422
        row = session.get(CreativeItem, uuid.UUID(str(item["id"])))
        assert row is not None
        assert row.workflow_status == CreativeWorkflowStatus.PENDING_VISUAL_REVIEW
        assert (
            list(
                session.scalars(
                    select(VisualReview).where(
                        VisualReview.visual_audit_id == uuid.UUID(str(audit_id))
                    )
                )
            )
            == []
        )
    finally:
        clear_visual_adapter_overrides()


def test_approve_with_high_finding_and_exception_persists_evidence(
    client: TestClient, session: Session
):
    workspace = make_workspace(session)
    item, _asset_id, audit_id = _setup_audited_asset(
        client, session, workspace, vision_payload=FAIL_HIGH_PAYLOAD
    )
    try:
        response = approve(
            client,
            workspace["tokens"][BrandRole.VISUAL_REVIEWER],
            audit_id,
            exception_accepted=True,
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["item"]["workflow_status"] == "FINAL_APPROVED"
        assert body["review"]["exception_accepted"] is True
        assert body["review"]["evidence"]["high_findings"][0]["rule_id"] == "rule-logo"
        assert body["review"]["evidence"]["high_findings"][0]["severity"] == "high"
    finally:
        clear_visual_adapter_overrides()


def test_request_changes_transitions_and_requires_new_version_to_reapprove(
    client: TestClient, session: Session
):
    workspace = make_workspace(session)
    item, asset_id, audit_id = _setup_audited_asset(client, session, workspace)
    try:
        reviewer_token = workspace["tokens"][BrandRole.VISUAL_REVIEWER]
        response = request_changes(client, reviewer_token, audit_id)

        assert response.status_code == 200
        assert response.json()["item"]["workflow_status"] == "VISUAL_CHANGES_REQUESTED"

        # Retrying approve on the SAME audit after request-changes: item is no
        # longer PENDING_VISUAL_REVIEW and there is no existing APPROVED
        # decision for this reviewer+audit yet, so it is a real 409 (not idempotent).
        second = approve(client, reviewer_token, audit_id)
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "INVALID_WORKFLOW_TRANSITION"
    finally:
        clear_visual_adapter_overrides()


def test_approve_retry_is_idempotent_no_duplicate_row(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item, _asset_id, audit_id = _setup_audited_asset(client, session, workspace)
    try:
        reviewer_token = workspace["tokens"][BrandRole.VISUAL_REVIEWER]
        first = approve(client, reviewer_token, audit_id)
        second = approve(client, reviewer_token, audit_id)

        assert first.status_code == second.status_code == 200
        assert first.json()["review"]["id"] == second.json()["review"]["id"]
        rows = list(
            session.scalars(
                select(VisualReview).where(VisualReview.visual_audit_id == uuid.UUID(str(audit_id)))
            )
        )
        assert len(rows) == 1
    finally:
        clear_visual_adapter_overrides()


def test_creator_cannot_decide(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item, _asset_id, audit_id = _setup_audited_asset(client, session, workspace)
    try:
        response = approve(client, workspace["tokens"][BrandRole.CREATOR], audit_id)
        assert response.status_code == 403
    finally:
        clear_visual_adapter_overrides()


def test_content_reviewer_cannot_decide(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item, _asset_id, audit_id = _setup_audited_asset(client, session, workspace)
    try:
        response = request_changes(
            client, workspace["tokens"][BrandRole.CONTENT_REVIEWER], audit_id
        )
        assert response.status_code == 403
    finally:
        clear_visual_adapter_overrides()


def test_decision_by_reviewer_of_another_brand_is_404(client: TestClient, session: Session):
    workspace = make_workspace(session)
    other = make_workspace(session, roles=(BrandRole.VISUAL_REVIEWER,))
    item, _asset_id, audit_id = _setup_audited_asset(client, session, workspace)
    try:
        response = approve(client, other["tokens"][BrandRole.VISUAL_REVIEWER], audit_id)
        assert response.status_code == 404
    finally:
        clear_visual_adapter_overrides()


def test_full_cycle_request_changes_new_version_approve(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item, asset_id, audit_id = _setup_audited_asset(client, session, workspace)
    try:
        creator_token = workspace["tokens"][BrandRole.CREATOR]
        reviewer_token = workspace["tokens"][BrandRole.VISUAL_REVIEWER]

        assert request_changes(client, reviewer_token, audit_id).status_code == 200

        upload_v2 = upload_visual(client, creator_token, item["id"], filename="hero-v2.png")
        assert upload_v2.status_code == 201, upload_v2.text
        row = session.get(CreativeItem, uuid.UUID(str(item["id"])))
        assert row is not None
        assert row.workflow_status == CreativeWorkflowStatus.PENDING_VISUAL_REVIEW

        audit2 = run_audit(client, reviewer_token, upload_v2.json()["id"])
        assert audit2.status_code == 200

        approved = approve(client, reviewer_token, audit2.json()["id"])
        assert approved.status_code == 200
        assert approved.json()["item"]["workflow_status"] == "FINAL_APPROVED"
    finally:
        clear_visual_adapter_overrides()
