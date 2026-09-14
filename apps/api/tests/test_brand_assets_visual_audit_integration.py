"""Cross-consumption (012-brand-assets task 3.1): visual-compliance's audit
flow resolves a brand's PRIMARY_LOGO through brand-assets' own read path
instead of reimplementing storage access for it.

Verifies (1) the audit persists a durable reference to the resolved
PRIMARY_LOGO once one exists, (2) an audit for a brand with no PRIMARY_LOGO
degrades to a null reference rather than failing, and (3) the SAME storage
adapter instance injected into the visual_audit router is the one that
resolves the logo's signed URL -- no second/independent storage adapter is
constructed for this."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.fakes import FakeEmbeddingModel, FakeVisionModel
from app.identity.models import BrandRole
from tests.conftest import auth_header, make_workspace, seed_synced_knowledge
from tests.test_brand_assets_api import clear_storage_override as clear_brand_assets_storage
from tests.test_brand_assets_api import install_storage as install_brand_assets_storage
from tests.test_brand_assets_api import upload_asset
from tests.test_visual_audit_service import audit_rows
from tests.test_visual_upload import (
    clear_visual_adapter_overrides,
    install_visual_adapters,
    make_approved_item,
    upload_visual,
)


def run_audit(client: TestClient, token: str, asset_id):
    return client.post(f"/api/v1/visual-assets/{asset_id}/audit", headers=auth_header(token))


def test_audit_records_the_brand_primary_logo_resolved_via_brand_assets(
    client: TestClient, session: Session
):
    workspace = make_workspace(session)
    creator_token = workspace["tokens"][BrandRole.CREATOR]

    # Upload the brand's PRIMARY_LOGO through the brand-assets endpoint,
    # sharing one FakeStorage instance with the visual_audit router so both
    # modules read/write the same fake object store (no live network either
    # way).
    storage = install_brand_assets_storage()
    install_visual_adapters(storage=storage)
    try:
        logo = upload_asset(client, creator_token, workspace["brand_id"]).json()
        assert logo["type"] == "PRIMARY_LOGO"

        item = make_approved_item(client, session, workspace)
        upload = upload_visual(client, creator_token, item["id"])
        assert upload.status_code == 201, upload.text
        asset_id = upload.json()["id"]

        seed_synced_knowledge(
            session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id
        )
        install_visual_adapters(
            storage=storage, vision=FakeVisionModel(), embedding=FakeEmbeddingModel()
        )

        # `storage.signed_url_calls` should show the primary logo's own path
        # got signed as part of this exact audit run (proof of the wiring),
        # not a fresh/independent adapter reading it separately.
        signed_calls_before = len(storage.signed_url_calls)

        response = run_audit(client, workspace["tokens"][BrandRole.VISUAL_REVIEWER], asset_id)
        assert response.status_code == 200, response.text

        signed_paths_during_audit = [
            call["path"] for call in storage.signed_url_calls[signed_calls_before:]
        ]
        logo_row = audit_rows(session, asset_id)[0]
        assert logo_row.applied_context["brand_primary_logo_asset_id"] == logo["id"]
        # The same storage instance resolved the logo's signed URL as part of
        # this audit call.
        assert any(
            path is not None and "brand-assets" in path for path in signed_paths_during_audit
        )
    finally:
        clear_visual_adapter_overrides()
        clear_brand_assets_storage()


def test_audit_without_a_primary_logo_uploaded_degrades_to_null_reference(
    client: TestClient, session: Session
):
    workspace = make_workspace(session)
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    item = make_approved_item(client, session, workspace)
    storage, _tracer = install_visual_adapters()
    try:
        upload = upload_visual(client, creator_token, item["id"])
        assert upload.status_code == 201
        asset_id = upload.json()["id"]

        seed_synced_knowledge(
            session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id
        )
        install_visual_adapters(
            storage=storage, vision=FakeVisionModel(), embedding=FakeEmbeddingModel()
        )

        response = run_audit(client, workspace["tokens"][BrandRole.VISUAL_REVIEWER], asset_id)
        assert response.status_code == 200, response.text

        row = audit_rows(session, asset_id)[0]
        assert row.applied_context["brand_primary_logo_asset_id"] is None
    finally:
        clear_visual_adapter_overrides()
