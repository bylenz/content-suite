"""Visual upload (008 task 5.1): membership-first, workflow-state guard,
validation, versioning and workflow transition + event."""

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.ports import EmbeddingModel, VisionModel
from app.creative.models import CreativeItem, CreativeWorkflowStatus, WorkflowEvent
from app.identity.models import BrandRole
from app.storage.fakes import FakeStorage
from app.visual_audit.models import VisualAsset
from app.visual_audit.router import (
    get_embedding_adapter,
    get_storage_adapter,
    get_tracer_adapter,
    get_vision_adapter,
)
from tests.conftest import auth_header, make_workspace
from tests.test_creative_items import create_item
from tests.test_creative_submit import force_status

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


class FakeTracer:
    def __init__(self) -> None:
        self.spans: list[Any] = []

    async def emit_span(self, span: Any) -> str | None:
        self.spans.append(span)
        return "trace-visual-test"


class FailingTracer:
    async def emit_span(self, span: Any) -> str | None:
        raise RuntimeError("tracer boom")


_UNSET = object()


def install_visual_adapters(
    *,
    storage: Any = _UNSET,
    vision: VisionModel | None = None,
    embedding: EmbeddingModel | None = None,
    tracer: Any = None,
) -> tuple[Any, Any]:
    """Override the visual_audit router composition roots with test doubles.

    `storage=None` explicitly simulates an unconfigured storage adapter (503);
    omitting it defaults to a fresh `FakeStorage()`. `storage`/return types are
    `Any` on purpose: callers pass either a `FakeStorage` (to inspect
    `.put_calls`/`.remove_calls`) or the sentinel `None`, which a precise
    `StoragePort | None` annotation cannot express through the sentinel check.
    """
    from app.main import app

    storage = FakeStorage() if storage is _UNSET else storage
    tracer = tracer if tracer is not None else FakeTracer()
    app.dependency_overrides[get_storage_adapter] = lambda: storage
    app.dependency_overrides[get_vision_adapter] = lambda: vision
    app.dependency_overrides[get_embedding_adapter] = lambda: embedding
    app.dependency_overrides[get_tracer_adapter] = lambda: tracer
    return storage, tracer


def clear_visual_adapter_overrides() -> None:
    from app.creative.router import get_embedding_adapter as creative_embedding
    from app.creative.router import get_text_adapter as creative_text
    from app.creative.router import get_tracer_adapter as creative_tracer
    from app.main import app

    for dep in (
        get_storage_adapter,
        get_vision_adapter,
        get_embedding_adapter,
        get_tracer_adapter,
        creative_embedding,
        creative_tracer,
        creative_text,
    ):
        app.dependency_overrides.pop(dep, None)


def make_approved_item(
    client: TestClient, session: Session, workspace: dict, *, brief: dict | None = None
) -> dict:
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, creator_token, workspace["brand_id"], brief=brief).json()
    force_status(session, item["id"], CreativeWorkflowStatus.CONTENT_APPROVED)
    return item


def upload_visual(
    client: TestClient,
    token: str,
    item_id,
    *,
    content: bytes = PNG_BYTES,
    filename: str = "hero.png",
    content_type: str = "image/png",
):
    return client.post(
        f"/api/v1/creative-items/{item_id}/visual-assets",
        headers=auth_header(token),
        files={"file": (filename, content, content_type)},
    )


def asset_rows(session: Session, item_id) -> list[VisualAsset]:
    return list(
        session.scalars(
            select(VisualAsset)
            .where(VisualAsset.creative_item_id == uuid.UUID(str(item_id)))
            .order_by(VisualAsset.version)
        )
    )


def test_upload_on_content_approved_creates_v1_and_transitions(
    client: TestClient, session: Session
):
    workspace = make_workspace(session)
    item = make_approved_item(client, session, workspace)
    storage, tracer = install_visual_adapters()
    try:
        response = upload_visual(client, workspace["tokens"][BrandRole.CREATOR], item["id"])
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["version"] == 1
        assert "storage_path" not in body
        assert body["signed_url"].startswith("fake-signed://")

        row = session.get(CreativeItem, uuid.UUID(str(item["id"])))
        assert row is not None
        assert row.workflow_status == CreativeWorkflowStatus.PENDING_VISUAL_REVIEW

        events = list(
            session.scalars(
                select(WorkflowEvent).where(
                    WorkflowEvent.creative_item_id == uuid.UUID(str(item["id"])),
                    WorkflowEvent.event_type == "VISUAL_UPLOADED",
                )
            )
        )
        assert len(events) == 1
        assert storage.put_calls[0]["content_type"] == "image/png"
    finally:
        clear_visual_adapter_overrides()


def test_upload_in_invalid_state_is_409(client: TestClient, session: Session):
    workspace = make_workspace(session)
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, creator_token, workspace["brand_id"]).json()  # stays DRAFT
    install_visual_adapters()
    try:
        response = upload_visual(client, creator_token, item["id"])
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "INVALID_WORKFLOW_TRANSITION"
        assert asset_rows(session, item["id"]) == []
    finally:
        clear_visual_adapter_overrides()


def test_upload_by_non_member_is_404(client: TestClient, session: Session):
    workspace = make_workspace(session)
    other = make_workspace(session, roles=(BrandRole.CREATOR,))
    item = make_approved_item(client, session, workspace)
    install_visual_adapters()
    try:
        response = upload_visual(client, other["tokens"][BrandRole.CREATOR], item["id"])
        assert response.status_code == 404
    finally:
        clear_visual_adapter_overrides()


def test_upload_by_content_reviewer_is_403(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item = make_approved_item(client, session, workspace)
    install_visual_adapters()
    try:
        response = upload_visual(
            client, workspace["tokens"][BrandRole.CONTENT_REVIEWER], item["id"]
        )
        assert response.status_code == 403
    finally:
        clear_visual_adapter_overrides()


def test_upload_invalid_file_is_422_no_orphans(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item = make_approved_item(client, session, workspace)
    storage, _tracer = install_visual_adapters()
    try:
        response = upload_visual(
            client,
            workspace["tokens"][BrandRole.CREATOR],
            item["id"],
            content=b"not an image, plain text",
            content_type="image/png",
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert asset_rows(session, item["id"]) == []
        assert storage.put_calls == []
    finally:
        clear_visual_adapter_overrides()


def test_upload_oversized_file_is_422(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item = make_approved_item(client, session, workspace)
    install_visual_adapters()
    try:
        big = PNG_BYTES + (b"\x00" * (6 * 1024 * 1024))
        response = upload_visual(
            client, workspace["tokens"][BrandRole.CREATOR], item["id"], content=big
        )
        assert response.status_code == 422
    finally:
        clear_visual_adapter_overrides()


def test_upload_without_storage_configured_is_503(client: TestClient, session: Session):
    workspace = make_workspace(session)
    item = make_approved_item(client, session, workspace)
    install_visual_adapters(storage=None)
    try:
        response = upload_visual(client, workspace["tokens"][BrandRole.CREATOR], item["id"])
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "STORAGE_UNAVAILABLE"
        assert asset_rows(session, item["id"]) == []
    finally:
        clear_visual_adapter_overrides()


def test_correction_after_changes_requested_creates_v2_and_keeps_v1_intact(
    client: TestClient, session: Session
):
    workspace = make_workspace(session)
    item = make_approved_item(client, session, workspace)
    install_visual_adapters()
    try:
        creator_token = workspace["tokens"][BrandRole.CREATOR]
        first = upload_visual(client, creator_token, item["id"])
        assert first.status_code == 201
        v1_path_snapshot = asset_rows(session, item["id"])[0].storage_path

        force_status(session, item["id"], CreativeWorkflowStatus.VISUAL_CHANGES_REQUESTED)
        second = upload_visual(
            client, creator_token, item["id"], filename="hero-v2.png"
        )
        assert second.status_code == 201, second.text
        assert second.json()["version"] == 2

        rows = asset_rows(session, item["id"])
        assert [r.version for r in rows] == [1, 2]
        assert rows[0].storage_path == v1_path_snapshot  # v1 untouched

        row = session.get(CreativeItem, uuid.UUID(str(item["id"])))
        assert row is not None
        assert row.workflow_status == CreativeWorkflowStatus.PENDING_VISUAL_REVIEW
    finally:
        clear_visual_adapter_overrides()
