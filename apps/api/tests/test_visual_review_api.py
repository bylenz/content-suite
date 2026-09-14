"""Visual Review API integration (008 task 6.1): queue, asset listing, history,
membership-first ordering, envelope shapes, no `storage_path` leak anywhere."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.fakes import FakeEmbeddingModel, FakeVisionModel
from app.identity.models import BrandRole
from tests.conftest import auth_header, make_workspace, seed_synced_knowledge
from tests.test_visual_audit_service import run_audit
from tests.test_visual_upload import (
    clear_visual_adapter_overrides,
    install_visual_adapters,
    make_approved_item,
    upload_visual,
)


def queue(client: TestClient, token: str):
    return client.get("/api/v1/visual-reviews/queue", headers=auth_header(token))


def list_assets(client: TestClient, token: str, item_id):
    return client.get(f"/api/v1/creative-items/{item_id}/visual-assets", headers=auth_header(token))


def history(client: TestClient, token: str, item_id):
    return client.get(
        f"/api/v1/creative-items/{item_id}/visual-audit-history", headers=auth_header(token)
    )


def test_queue_lists_pending_visual_review_items_scoped_by_brand(
    client: TestClient, session: Session
):
    workspace_a = make_workspace(session)
    workspace_b = make_workspace(session)
    item_a = make_approved_item(client, session, workspace_a)
    item_b = make_approved_item(client, session, workspace_b)
    storage, _tracer = install_visual_adapters()
    try:
        upload_a = upload_visual(client, workspace_a["tokens"][BrandRole.CREATOR], item_a["id"])
        upload_b = upload_visual(client, workspace_b["tokens"][BrandRole.CREATOR], item_b["id"])
        assert upload_a.status_code == 201
        assert upload_b.status_code == 201

        response = queue(client, workspace_a["tokens"][BrandRole.VISUAL_REVIEWER])

        assert response.status_code == 200
        ids = [row["item"]["id"] for row in response.json()["items"]]
        assert ids == [item_a["id"]]  # never leaks workspace_b's item
        assert "signed_url" in response.json()["items"][0]["asset"]
        assert "storage_path" not in response.json()["items"][0]["asset"]
    finally:
        clear_visual_adapter_overrides()


def test_queue_creator_gets_403_when_their_brand_has_a_pending_item(
    client: TestClient, session: Session
):
    """A CREATOR's own role check only fires once an item from their brand is
    actually in the queue (mirrors governance's `content-reviews/queue`
    convention: an empty cross-brand queue never evaluates the role gate)."""
    workspace = make_workspace(session)
    item = make_approved_item(client, session, workspace)
    install_visual_adapters()
    try:
        upload = upload_visual(client, workspace["tokens"][BrandRole.CREATOR], item["id"])
        assert upload.status_code == 201

        response = queue(client, workspace["tokens"][BrandRole.CREATOR])

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"
    finally:
        clear_visual_adapter_overrides()


def test_queue_creator_with_no_pending_items_anywhere_is_an_empty_200(
    client: TestClient, session: Session
):
    workspace = make_workspace(session)
    install_visual_adapters()
    try:
        response = queue(client, workspace["tokens"][BrandRole.CREATOR])
        assert response.status_code == 200
        assert response.json()["items"] == []
    finally:
        clear_visual_adapter_overrides()


def test_list_assets_membership_first_404_for_nonmember(client: TestClient, session: Session):
    workspace = make_workspace(session)
    other = make_workspace(session, roles=(BrandRole.CREATOR,))
    item = make_approved_item(client, session, workspace)
    install_visual_adapters()
    try:
        response = list_assets(client, other["tokens"][BrandRole.CREATOR], item["id"])
        assert response.status_code == 404
    finally:
        clear_visual_adapter_overrides()


def test_list_assets_never_exposes_storage_path(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item = make_approved_item(client, session, workspace)
    install_visual_adapters()
    try:
        creator_token = workspace["tokens"][BrandRole.CREATOR]
        assert upload_visual(client, creator_token, item["id"]).status_code == 201

        response = list_assets(client, creator_token, item["id"])

        assert response.status_code == 200
        body = response.json()
        assert len(body["assets"]) == 1
        assert body["assets"][0]["signed_url"].startswith("fake-signed://")
        assert "storage_path" not in body["assets"][0]
    finally:
        clear_visual_adapter_overrides()


def test_history_lists_versions_audits_and_reviews(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item = make_approved_item(client, session, workspace)
    storage, _tracer = install_visual_adapters()
    try:
        creator_token = workspace["tokens"][BrandRole.CREATOR]
        reviewer_token = workspace["tokens"][BrandRole.VISUAL_REVIEWER]
        upload = upload_visual(client, creator_token, item["id"])
        assert upload.status_code == 201
        asset_id = upload.json()["id"]

        seed_synced_knowledge(
            session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id
        )
        install_visual_adapters(
            storage=storage, vision=FakeVisionModel(), embedding=FakeEmbeddingModel()
        )
        audit = run_audit(client, reviewer_token, asset_id)
        assert audit.status_code == 200

        response = history(client, creator_token, item["id"])

        assert response.status_code == 200
        body = response.json()
        assert len(body["entries"]) == 1
        assert len(body["entries"][0]["audits"]) == 1
        assert "storage_path" not in body["entries"][0]["asset"]
    finally:
        clear_visual_adapter_overrides()


def test_history_membership_first_404(client: TestClient, session: Session):
    workspace = make_workspace(session)
    other = make_workspace(session, roles=(BrandRole.VISUAL_REVIEWER,))
    item = make_approved_item(client, session, workspace)
    install_visual_adapters()
    try:
        response = history(client, other["tokens"][BrandRole.VISUAL_REVIEWER], item["id"])
        assert response.status_code == 404
    finally:
        clear_visual_adapter_overrides()


def test_list_assets_with_no_assets_never_requires_storage(client: TestClient, session: Session):
    """Regression (found via manual verification, task 8.3): an item with no
    visuals yet must be servable even when storage is entirely unconfigured
    -- there is no signed URL to compute for an empty list."""
    workspace = make_workspace(session)
    item = make_approved_item(client, session, workspace)
    install_visual_adapters(storage=None)
    try:
        response = list_assets(client, workspace["tokens"][BrandRole.CREATOR], item["id"])
        assert response.status_code == 200
        assert response.json()["assets"] == []
    finally:
        clear_visual_adapter_overrides()


def test_history_with_no_assets_never_requires_storage(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item = make_approved_item(client, session, workspace)
    install_visual_adapters(storage=None)
    try:
        response = history(client, workspace["tokens"][BrandRole.CREATOR], item["id"])
        assert response.status_code == 200
        assert response.json()["entries"] == []
    finally:
        clear_visual_adapter_overrides()


def test_list_assets_with_an_asset_still_needs_storage(client: TestClient, session: Session):
    """The flip side of the regression above: once a real asset exists, its
    signed URL still requires storage -- the fix narrows the guard, it does
    not remove it."""
    workspace = make_workspace(session)
    item = make_approved_item(client, session, workspace)
    install_visual_adapters()
    try:
        creator_token = workspace["tokens"][BrandRole.CREATOR]
        assert upload_visual(client, creator_token, item["id"]).status_code == 201
    finally:
        clear_visual_adapter_overrides()

    install_visual_adapters(storage=None)
    try:
        response = list_assets(client, workspace["tokens"][BrandRole.CREATOR], item["id"])
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "STORAGE_UNAVAILABLE"
    finally:
        clear_visual_adapter_overrides()


def test_all_visual_endpoints_error_envelope_shape_on_403(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item = make_approved_item(client, session, workspace)
    install_visual_adapters()
    try:
        upload = upload_visual(client, workspace["tokens"][BrandRole.CREATOR], item["id"])
        assert upload.status_code == 201
        response = queue(client, workspace["tokens"][BrandRole.CREATOR])
        assert response.status_code == 403
        body = response.json()
        assert set(body["error"].keys()) == {"code", "message", "details"}
    finally:
        clear_visual_adapter_overrides()
