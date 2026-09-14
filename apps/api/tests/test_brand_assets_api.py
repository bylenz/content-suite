"""Brand Assets endpoints (012-brand-assets tasks 2.1/2.2/2.3): slot vs.
collection semantics, signed-URL-only responses, and the 403-vs-404
authorization split design.md fixes (mirrors 011-creative-studio's
create_item/_resolve_item precedent)."""

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brand_assets.models import BrandAsset
from app.brand_assets.router import get_storage_adapter
from app.brand_dna.models import BrandDnaStatus, BrandDnaVersion, KnowledgeStatus
from app.identity.models import BrandRole
from app.storage.fakes import FakeStorage
from tests.conftest import auth_header, make_workspace, valid_document

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 32

_UNSET = object()


def install_storage(storage: Any = _UNSET) -> Any:
    from app.main import app

    storage = FakeStorage() if storage is _UNSET else storage
    app.dependency_overrides[get_storage_adapter] = lambda: storage
    return storage


def clear_storage_override() -> None:
    from app.main import app

    app.dependency_overrides.pop(get_storage_adapter, None)


def upload_asset(
    client: TestClient,
    token: str,
    brand_id,
    *,
    asset_type: str = "PRIMARY_LOGO",
    content: bytes = PNG_BYTES,
    filename: str = "logo.png",
    content_type: str = "image/png",
):
    return client.post(
        f"/api/v1/brands/{brand_id}/assets",
        headers=auth_header(token),
        data={"type": asset_type},
        files={"file": (filename, content, content_type)},
    )


def list_assets(client: TestClient, token: str, brand_id):
    return client.get(f"/api/v1/brands/{brand_id}/assets", headers=auth_header(token))


def delete_asset(client: TestClient, token: str, brand_id, asset_id):
    return client.delete(
        f"/api/v1/brands/{brand_id}/assets/{asset_id}", headers=auth_header(token)
    )


def rows_for_brand(session: Session, brand_id) -> list[BrandAsset]:
    return list(
        session.scalars(
            select(BrandAsset)
            .where(BrandAsset.brand_id == uuid.UUID(str(brand_id)))
            .order_by(BrandAsset.created_at, BrandAsset.id)
        )
    )


def test_first_primary_logo_upload_creates_the_only_row(client: TestClient, session: Session):
    workspace = make_workspace(session)
    install_storage()
    try:
        creator_token = workspace["tokens"][BrandRole.CREATOR]
        response = upload_asset(client, creator_token, workspace["brand_id"])
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["type"] == "PRIMARY_LOGO"
        assert "storage_path" not in body
        assert body["signed_url"].startswith("fake-signed://")
        assert body["brand_dna_version_id"] is None

        rows = rows_for_brand(session, workspace["brand_id"])
        assert len(rows) == 1
    finally:
        clear_storage_override()


def test_replacing_primary_logo_deletes_old_row_and_object(client: TestClient, session: Session):
    workspace = make_workspace(session)
    storage = install_storage()
    try:
        creator_token = workspace["tokens"][BrandRole.CREATOR]
        first = upload_asset(client, creator_token, workspace["brand_id"])
        assert first.status_code == 201
        first_id = first.json()["id"]

        second = upload_asset(client, creator_token, workspace["brand_id"], filename="logo-v2.png")
        assert second.status_code == 201, second.text
        second_id = second.json()["id"]
        assert second_id != first_id

        rows = rows_for_brand(session, workspace["brand_id"])
        assert len(rows) == 1  # never two PRIMARY_LOGO rows at once
        assert str(rows[0].id) == second_id
        assert storage.remove_calls  # old object cleaned up
    finally:
        clear_storage_override()


def test_primary_and_alt_logo_are_independent_slots(client: TestClient, session: Session):
    workspace = make_workspace(session)
    install_storage()
    try:
        creator_token = workspace["tokens"][BrandRole.CREATOR]
        primary = upload_asset(
            client, creator_token, workspace["brand_id"], asset_type="PRIMARY_LOGO"
        )
        alt = upload_asset(client, creator_token, workspace["brand_id"], asset_type="ALT_LOGO")
        assert primary.status_code == 201
        assert alt.status_code == 201

        rows = rows_for_brand(session, workspace["brand_id"])
        assert {r.type.value for r in rows} == {"PRIMARY_LOGO", "ALT_LOGO"}
        assert len(rows) == 2
    finally:
        clear_storage_override()


def test_multiple_visual_references_coexist_and_list_together(
    client: TestClient, session: Session
):
    workspace = make_workspace(session)
    install_storage()
    try:
        creator_token = workspace["tokens"][BrandRole.CREATOR]
        for name in ("ref1.png", "ref2.png", "ref3.png"):
            response = upload_asset(
                client,
                creator_token,
                workspace["brand_id"],
                asset_type="VISUAL_REFERENCE",
                filename=name,
            )
            assert response.status_code == 201, response.text

        rows = rows_for_brand(session, workspace["brand_id"])
        assert len(rows) == 3
        assert all(r.type.value == "VISUAL_REFERENCE" for r in rows)

        listed = list_assets(client, creator_token, workspace["brand_id"])
        assert listed.status_code == 200
        assert len(listed.json()["assets"]) == 3
    finally:
        clear_storage_override()


def test_deleting_one_visual_reference_leaves_the_rest_and_logos_intact(
    client: TestClient, session: Session
):
    workspace = make_workspace(session)
    storage = install_storage()
    try:
        creator_token = workspace["tokens"][BrandRole.CREATOR]
        upload_asset(client, creator_token, workspace["brand_id"], asset_type="PRIMARY_LOGO")
        ref_a = upload_asset(
            client,
            creator_token,
            workspace["brand_id"],
            asset_type="VISUAL_REFERENCE",
            filename="a.png",
        ).json()
        ref_b = upload_asset(
            client,
            creator_token,
            workspace["brand_id"],
            asset_type="VISUAL_REFERENCE",
            filename="b.png",
        ).json()

        response = delete_asset(client, creator_token, workspace["brand_id"], ref_a["id"])
        assert response.status_code == 204

        rows = rows_for_brand(session, workspace["brand_id"])
        remaining_ids = {str(r.id) for r in rows}
        assert ref_a["id"] not in remaining_ids
        assert ref_b["id"] in remaining_ids
        assert any(r.type.value == "PRIMARY_LOGO" for r in rows)
        assert storage.remove_calls  # the deleted reference's object was cleaned up
    finally:
        clear_storage_override()


def test_list_readable_by_any_member_role(client: TestClient, session: Session):
    workspace = make_workspace(session)
    install_storage()
    try:
        creator_token = workspace["tokens"][BrandRole.CREATOR]
        upload_asset(client, creator_token, workspace["brand_id"])

        for role in (BrandRole.CONTENT_REVIEWER, BrandRole.VISUAL_REVIEWER):
            response = list_assets(client, workspace["tokens"][role], workspace["brand_id"])
            assert response.status_code == 200, response.text
            assert len(response.json()["assets"]) == 1
    finally:
        clear_storage_override()


def test_list_without_membership_is_403(client: TestClient, session: Session):
    workspace = make_workspace(session)
    other = make_workspace(session, roles=(BrandRole.CREATOR,))
    install_storage()
    try:
        response = list_assets(client, other["tokens"][BrandRole.CREATOR], workspace["brand_id"])
        assert response.status_code == 403
    finally:
        clear_storage_override()


def test_upload_without_membership_is_403(client: TestClient, session: Session):
    workspace = make_workspace(session)
    other = make_workspace(session, roles=(BrandRole.CREATOR,))
    install_storage()
    try:
        response = upload_asset(client, other["tokens"][BrandRole.CREATOR], workspace["brand_id"])
        assert response.status_code == 403
    finally:
        clear_storage_override()


def test_reviewer_cannot_upload_or_delete(client: TestClient, session: Session):
    workspace = make_workspace(session)
    install_storage()
    try:
        creator_token = workspace["tokens"][BrandRole.CREATOR]
        asset = upload_asset(client, creator_token, workspace["brand_id"]).json()

        for role in (BrandRole.CONTENT_REVIEWER, BrandRole.VISUAL_REVIEWER):
            upload_response = upload_asset(
                client, workspace["tokens"][role], workspace["brand_id"], asset_type="ALT_LOGO"
            )
            assert upload_response.status_code == 403

            delete_response = delete_asset(
                client, workspace["tokens"][role], workspace["brand_id"], asset["id"]
            )
            assert delete_response.status_code == 403

        # Nothing was persisted or removed by the denied attempts.
        rows = rows_for_brand(session, workspace["brand_id"])
        assert len(rows) == 1
    finally:
        clear_storage_override()


def test_delete_nonexistent_asset_is_404(client: TestClient, session: Session):
    workspace = make_workspace(session)
    install_storage()
    try:
        response = delete_asset(
            client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"], uuid.uuid4()
        )
        assert response.status_code == 404
    finally:
        clear_storage_override()


def test_delete_asset_belonging_to_another_brand_is_404(client: TestClient, session: Session):
    workspace = make_workspace(session)
    other = make_workspace(session)
    install_storage()
    try:
        asset = upload_asset(
            client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"]
        ).json()
        # Delete via the OTHER brand's path with its own CREATOR token.
        response = delete_asset(
            client, other["tokens"][BrandRole.CREATOR], other["brand_id"], asset["id"]
        )
        assert response.status_code == 404
    finally:
        clear_storage_override()


def test_delete_without_membership_is_404(client: TestClient, session: Session):
    workspace = make_workspace(session)
    outsider = make_workspace(session, roles=(BrandRole.CREATOR,))
    install_storage()
    try:
        asset = upload_asset(
            client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"]
        ).json()
        response = delete_asset(
            client, outsider["tokens"][BrandRole.CREATOR], workspace["brand_id"], asset["id"]
        )
        assert response.status_code == 404
    finally:
        clear_storage_override()


def test_delete_removes_row_and_storage_object(client: TestClient, session: Session):
    workspace = make_workspace(session)
    storage = install_storage()
    try:
        creator_token = workspace["tokens"][BrandRole.CREATOR]
        asset = upload_asset(client, creator_token, workspace["brand_id"]).json()
        path = storage.put_calls[0]["path"]
        assert storage.object_exists(path)

        response = delete_asset(client, creator_token, workspace["brand_id"], asset["id"])
        assert response.status_code == 204
        assert rows_for_brand(session, workspace["brand_id"]) == []
        assert not storage.object_exists(path)
    finally:
        clear_storage_override()


def test_upload_invalid_file_is_422_no_row_no_orphan(client: TestClient, session: Session):
    workspace = make_workspace(session)
    storage = install_storage()
    try:
        response = upload_asset(
            client,
            workspace["tokens"][BrandRole.CREATOR],
            workspace["brand_id"],
            content=b"not an image, plain text",
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert rows_for_brand(session, workspace["brand_id"]) == []
        assert storage.put_calls == []
    finally:
        clear_storage_override()


def test_upload_oversized_file_is_422(client: TestClient, session: Session):
    workspace = make_workspace(session)
    install_storage()
    try:
        big = PNG_BYTES + (b"\x00" * (6 * 1024 * 1024))
        response = upload_asset(
            client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"], content=big
        )
        assert response.status_code == 422
    finally:
        clear_storage_override()


def test_upload_without_storage_configured_is_503(client: TestClient, session: Session):
    workspace = make_workspace(session)
    install_storage(storage=None)
    try:
        response = upload_asset(
            client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"]
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "STORAGE_UNAVAILABLE"
        assert rows_for_brand(session, workspace["brand_id"]) == []
    finally:
        clear_storage_override()


def test_list_without_storage_configured_is_503_when_assets_exist(
    client: TestClient, session: Session
):
    workspace = make_workspace(session)
    install_storage()
    try:
        upload_asset(client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"])
    finally:
        clear_storage_override()
    install_storage(storage=None)
    try:
        creator_token = workspace["tokens"][BrandRole.CREATOR]
        response = list_assets(client, creator_token, workspace["brand_id"])
        assert response.status_code == 503
    finally:
        clear_storage_override()


def test_list_without_storage_configured_is_200_when_empty(client: TestClient, session: Session):
    workspace = make_workspace(session)
    install_storage(storage=None)
    try:
        creator_token = workspace["tokens"][BrandRole.CREATOR]
        response = list_assets(client, creator_token, workspace["brand_id"])
        assert response.status_code == 200
        assert response.json()["assets"] == []
    finally:
        clear_storage_override()


def test_upload_captures_active_brand_dna_version_snapshot(client: TestClient, session: Session):
    workspace = make_workspace(session)
    creator_id = workspace["profiles"][BrandRole.CREATOR].id
    active = BrandDnaVersion(
        id=uuid.uuid4(),
        brand_id=workspace["brand_id"],
        version=1,
        status=BrandDnaStatus.ACTIVE,
        document=valid_document(),
        created_by=creator_id,
        knowledge_status=KnowledgeStatus.NOT_SYNCED,
    )
    session.add(active)
    session.commit()
    install_storage()
    try:
        response = upload_asset(
            client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"]
        )
        assert response.status_code == 201
        assert response.json()["brand_dna_version_id"] == str(active.id)
    finally:
        clear_storage_override()


def test_snapshot_stays_pinned_after_a_new_brand_dna_version_publishes(
    client: TestClient, session: Session
):
    """design.md: the link is an audit snapshot, not an ownership relation --
    it never updates retroactively when a newer Brand DNA version publishes."""
    workspace = make_workspace(session)
    creator_id = workspace["profiles"][BrandRole.CREATOR].id
    v1 = BrandDnaVersion(
        id=uuid.uuid4(),
        brand_id=workspace["brand_id"],
        version=1,
        status=BrandDnaStatus.ACTIVE,
        document=valid_document(),
        created_by=creator_id,
        knowledge_status=KnowledgeStatus.NOT_SYNCED,
    )
    session.add(v1)
    session.commit()
    install_storage()
    try:
        uploaded = upload_asset(
            client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"]
        ).json()
        assert uploaded["brand_dna_version_id"] == str(v1.id)

        # Publish a newer ACTIVE version.
        v1_row = session.get(BrandDnaVersion, v1.id)
        assert v1_row is not None
        v1_row.status = BrandDnaStatus.ARCHIVED
        v2 = BrandDnaVersion(
            id=uuid.uuid4(),
            brand_id=workspace["brand_id"],
            version=2,
            status=BrandDnaStatus.ACTIVE,
            document=valid_document(),
            created_by=creator_id,
            knowledge_status=KnowledgeStatus.NOT_SYNCED,
        )
        session.add(v2)
        session.commit()

        listed = list_assets(
            client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"]
        ).json()
        assert listed["assets"][0]["brand_dna_version_id"] == str(v1.id)  # unchanged
    finally:
        clear_storage_override()
