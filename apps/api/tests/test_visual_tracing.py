"""Visual audit tracing (008 task 6.2): sanitized `visual.upload`/`visual.audit`
spans via the Tracer port, and tracer-failure tolerance (mirrors
`test_knowledge_tracing.py`'s pattern)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.fakes import FakeEmbeddingModel, FakeVisionModel
from app.identity.models import BrandRole
from tests.conftest import make_workspace, seed_synced_knowledge
from tests.test_visual_audit_service import run_audit
from tests.test_visual_upload import (
    FailingTracer,
    clear_visual_adapter_overrides,
    install_visual_adapters,
    make_approved_item,
    upload_visual,
)


def test_upload_emits_a_sanitized_visual_upload_span(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item = make_approved_item(client, session, workspace)
    storage, tracer = install_visual_adapters()
    try:
        response = upload_visual(client, workspace["tokens"][BrandRole.CREATOR], item["id"])
        assert response.status_code == 201

        upload_spans = [s for s in tracer.spans if s.operation == "visual.upload"]
        assert len(upload_spans) == 1
        span = upload_spans[0]
        assert span.entity_type == "visual_asset"
        assert span.entity_id == response.json()["id"]
        assert span.brand_id == str(item["brand_id"])
        assert span.latency_ms >= 0
        # Never raw payloads: only scalar identity/latency fields travel.
        assert span.summary is None
        assert span.error is None
    finally:
        clear_visual_adapter_overrides()


def test_audit_emits_a_sanitized_visual_audit_span_with_bounded_summary(
    client: TestClient, session: Session
):
    workspace = make_workspace(session)
    item = make_approved_item(client, session, workspace)
    storage, tracer = install_visual_adapters()
    try:
        creator_token = workspace["tokens"][BrandRole.CREATOR]
        upload = upload_visual(client, creator_token, item["id"])
        assert upload.status_code == 201
        asset_id = upload.json()["id"]

        seed_synced_knowledge(
            session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id
        )
        install_visual_adapters(
            storage=storage,
            vision=FakeVisionModel(),
            embedding=FakeEmbeddingModel(),
            tracer=tracer,
        )

        audit_response = run_audit(client, workspace["tokens"][BrandRole.VISUAL_REVIEWER], asset_id)
        assert audit_response.status_code == 200

        audit_spans = [s for s in tracer.spans if s.operation == "visual.audit"]
        assert len(audit_spans) == 1
        span = audit_spans[0]
        assert span.entity_type == "visual_audit"
        assert span.entity_id == audit_response.json()["id"]
        assert span.model == "fake-vision-model"
        assert span.summary is not None
        assert span.summary.contract == "VisualAuditResult"
        assert span.summary.finding_count == 0
        # Sanitized: no findings content, no image/prompt payloads on the span.
        assert not hasattr(span, "findings")
        assert not hasattr(span, "image_ref")
    finally:
        clear_visual_adapter_overrides()


def test_upload_survives_tracer_failure(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item = make_approved_item(client, session, workspace)
    install_visual_adapters(tracer=FailingTracer())
    try:
        response = upload_visual(client, workspace["tokens"][BrandRole.CREATOR], item["id"])
        assert response.status_code == 201  # domain operation still succeeds
    finally:
        clear_visual_adapter_overrides()


def test_audit_survives_tracer_failure(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item = make_approved_item(client, session, workspace)
    storage, _tracer = install_visual_adapters()
    try:
        creator_token = workspace["tokens"][BrandRole.CREATOR]
        upload = upload_visual(client, creator_token, item["id"])
        assert upload.status_code == 201
        asset_id = upload.json()["id"]

        seed_synced_knowledge(
            session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id
        )
        install_visual_adapters(
            storage=storage,
            vision=FakeVisionModel(),
            embedding=FakeEmbeddingModel(),
            tracer=FailingTracer(),
        )

        response = run_audit(client, workspace["tokens"][BrandRole.VISUAL_REVIEWER], asset_id)
        assert response.status_code == 200  # domain operation still succeeds
    finally:
        clear_visual_adapter_overrides()
