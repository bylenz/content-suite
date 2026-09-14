"""Visual audit run (008 task 5.2): Vision invocation, fail-safe Knowledge
guard, invalid-output 503, deterministic score persistence, re-audit
non-mutation."""

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.fakes import FakeEmbeddingModel, FakeVisionModel
from app.identity.models import BrandRole
from app.visual_audit.models import VisualAudit
from tests.conftest import auth_header, make_workspace, seed_synced_knowledge
from tests.test_visual_upload import (
    clear_visual_adapter_overrides,
    install_visual_adapters,
    make_approved_item,
    upload_visual,
)

FAIL_HIGH_PAYLOAD = {
    "checks": [{"check_id": "check-logo", "label": "Logo usage", "status": "fail"}],
    "findings": [
        {
            "rule_id": "rule-logo",
            "category": "logo_usage",
            "expected": "Logo top-left with clear space",
            "detected": "Logo missing entirely",
            "evidence": "No logo visible in the frame",
            "recommendation": "Add the logo per brand guidelines",
            "severity": "high",
            "status": "fail",
        }
    ],
    "summary": "El visual omite el logo obligatorio.",
}


def run_audit(client: TestClient, token: str, asset_id):
    return client.post(f"/api/v1/visual-assets/{asset_id}/audit", headers=auth_header(token))


def read_audit(client: TestClient, token: str, asset_id):
    return client.get(f"/api/v1/visual-assets/{asset_id}/audit", headers=auth_header(token))


def _upload_and_get_asset_id(client: TestClient, session: Session, workspace: dict):
    """Returns (item_id, asset_id, storage) -- the SAME FakeStorage instance
    the upload used, so a later `install_visual_adapters(storage=storage, ...)`
    for the audit call can still resolve the uploaded object's signed URL."""
    item = make_approved_item(client, session, workspace)
    storage, _tracer = install_visual_adapters()
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    upload = upload_visual(client, creator_token, item["id"])
    assert upload.status_code == 201, upload.text
    return item["id"], upload.json()["id"], storage


def audit_rows(session: Session, asset_id: str) -> list[VisualAudit]:
    return list(
        session.scalars(
            select(VisualAudit)
            .where(VisualAudit.visual_asset_id == uuid.UUID(str(asset_id)))
            .order_by(VisualAudit.created_at)
        )
    )


def test_audit_happy_path_persists_findings_score_and_trace(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item_id, asset_id, storage = _upload_and_get_asset_id(client, session, workspace)
    try:
        seed_synced_knowledge(
            session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id
        )
        vision = FakeVisionModel()
        install_visual_adapters(storage=storage, vision=vision, embedding=FakeEmbeddingModel())

        response = run_audit(client, workspace["tokens"][BrandRole.VISUAL_REVIEWER], asset_id)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["score"] == 100.0  # default fake payload has no fail findings
        assert body["findings"] == []
        assert vision.calls[0]["op"] == "analyze_structured"
        assert vision.calls[0]["image_ref"].startswith("fake-signed://")

        rows = audit_rows(session, asset_id)
        assert len(rows) == 1
        assert str(rows[0].brand_dna_version_id) == body["brand_dna_version_id"]
    finally:
        clear_visual_adapter_overrides()


def test_audit_score_reflects_high_fail_finding(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item_id, asset_id, storage = _upload_and_get_asset_id(client, session, workspace)
    try:
        seed_synced_knowledge(
            session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id
        )
        install_visual_adapters(
            storage=storage,
            vision=FakeVisionModel(structured_output=FAIL_HIGH_PAYLOAD),
            embedding=FakeEmbeddingModel(),
        )

        response = run_audit(client, workspace["tokens"][BrandRole.VISUAL_REVIEWER], asset_id)

        assert response.status_code == 200
        body = response.json()
        assert body["score"] == 75.0  # 100 - 25 (HIGH)
        assert body["findings"][0]["severity"] == "high"
    finally:
        clear_visual_adapter_overrides()


def test_audit_without_synced_knowledge_is_503_no_persist(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item_id, asset_id, storage = _upload_and_get_asset_id(client, session, workspace)
    try:
        # No seed_synced_knowledge call: no ACTIVE Brand DNA version at all.
        vision = FakeVisionModel()
        install_visual_adapters(storage=storage, vision=vision, embedding=FakeEmbeddingModel())

        response = run_audit(client, workspace["tokens"][BrandRole.VISUAL_REVIEWER], asset_id)

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "KNOWLEDGE_NOT_AVAILABLE"
        assert vision.calls == []
        assert audit_rows(session, asset_id) == []
    finally:
        clear_visual_adapter_overrides()


def test_audit_with_invalid_vision_output_is_503_no_persist(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item_id, asset_id, storage = _upload_and_get_asset_id(client, session, workspace)
    try:
        seed_synced_knowledge(
            session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id
        )
        bad_payload = {"checks": [], "findings": [{"rule_id": "r1"}], "summary": "x"}
        install_visual_adapters(
            storage=storage,
            vision=FakeVisionModel(structured_output=bad_payload),
            embedding=FakeEmbeddingModel(),
        )

        response = run_audit(client, workspace["tokens"][BrandRole.VISUAL_REVIEWER], asset_id)

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "VISION_OUTPUT_INVALID"
        assert audit_rows(session, asset_id) == []
    finally:
        clear_visual_adapter_overrides()


def test_audit_without_vision_provider_configured_is_503(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item_id, asset_id, storage = _upload_and_get_asset_id(client, session, workspace)
    try:
        seed_synced_knowledge(
            session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id
        )
        install_visual_adapters(storage=storage, vision=None, embedding=FakeEmbeddingModel())

        response = run_audit(client, workspace["tokens"][BrandRole.VISUAL_REVIEWER], asset_id)

        assert response.status_code == 503
        assert audit_rows(session, asset_id) == []
    finally:
        clear_visual_adapter_overrides()


def test_reaudit_creates_new_record_and_keeps_previous_intact(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item_id, asset_id, storage = _upload_and_get_asset_id(client, session, workspace)
    try:
        seed_synced_knowledge(
            session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id
        )
        install_visual_adapters(
            storage=storage, vision=FakeVisionModel(), embedding=FakeEmbeddingModel()
        )
        reviewer_token = workspace["tokens"][BrandRole.VISUAL_REVIEWER]

        first = run_audit(client, reviewer_token, asset_id)
        assert first.status_code == 200
        # SQLite's CURRENT_TIMESTAMP is second-resolution (same caveat
        # documented in tests/test_governance_review.py's `_stamp_new_events`):
        # two audits issued back-to-back in one test can tie on `created_at`,
        # and the id-desc tiebreak does not track call order. Backdate the
        # first row so "most recent" is unambiguous; PostgreSQL's microsecond
        # `now()` never hits this in production.
        first_row = session.get(VisualAudit, uuid.UUID(str(first.json()["id"])))
        assert first_row is not None
        first_row.created_at = first_row.created_at - timedelta(seconds=5)
        session.commit()

        second = run_audit(client, reviewer_token, asset_id)
        assert second.status_code == 200
        assert first.json()["id"] != second.json()["id"]

        rows = audit_rows(session, asset_id)
        assert len(rows) == 2
        # GET returns the most recent one.
        latest = read_audit(client, reviewer_token, asset_id)
        assert latest.json()["id"] == second.json()["id"]
    finally:
        clear_visual_adapter_overrides()


def test_get_audit_without_any_audit_yet_is_404(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item_id, asset_id, storage = _upload_and_get_asset_id(client, session, workspace)
    try:
        response = read_audit(client, workspace["tokens"][BrandRole.VISUAL_REVIEWER], asset_id)
        assert response.status_code == 404
    finally:
        clear_visual_adapter_overrides()


def test_content_reviewer_cannot_trigger_audit(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item_id, asset_id, storage = _upload_and_get_asset_id(client, session, workspace)
    try:
        seed_synced_knowledge(
            session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id
        )
        install_visual_adapters(
            storage=storage, vision=FakeVisionModel(), embedding=FakeEmbeddingModel()
        )
        response = run_audit(client, workspace["tokens"][BrandRole.CONTENT_REVIEWER], asset_id)
        assert response.status_code == 403
    finally:
        clear_visual_adapter_overrides()
