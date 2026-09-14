"""Content Pipeline breakdown (change 014): `GET /creative-items/pipeline` exposes
all 7 real `workflow_status` values with an explicit zero for empty states —
never the 4-category mockup grouping (design.md) — and is membership-first."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.creative.models import CreativeItem, CreativeWorkflowStatus
from app.identity.models import BrandRole
from tests.conftest import auth_header, make_workspace
from tests.test_creative_items import create_item

ALL_STATUSES = {status.value for status in CreativeWorkflowStatus}


def test_pipeline_exposes_all_seven_states_with_explicit_zero(
    client: TestClient, session: Session
):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    brand_id = workspace["brand_id"]

    created_ids = [
        uuid.UUID(create_item(client, token, brand_id, title=f"Item {i}").json()["id"])
        for i in range(3)
    ]
    # No visual-review flow exists yet to reach every state through the API;
    # setting `workflow_status` directly here only prepares the fixture.
    items = list(session.scalars(select(CreativeItem).where(CreativeItem.id.in_(created_ids))))
    items[0].workflow_status = CreativeWorkflowStatus.PENDING_CONTENT_REVIEW
    items[1].workflow_status = CreativeWorkflowStatus.FINAL_APPROVED
    session.commit()

    response = client.get(
        f"/api/v1/creative-items/pipeline?brand_id={brand_id}", headers=auth_header(token)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["brand_id"] == str(brand_id)
    assert set(body["counts"]) == ALL_STATUSES  # exact allowlist, never a 4-category grouping
    assert body["counts"]["DRAFT"] == 1
    assert body["counts"]["PENDING_CONTENT_REVIEW"] == 1
    assert body["counts"]["FINAL_APPROVED"] == 1
    assert body["counts"]["CONTENT_CHANGES_REQUESTED"] == 0
    assert body["counts"]["CONTENT_APPROVED"] == 0
    assert body["counts"]["PENDING_VISUAL_REVIEW"] == 0
    assert body["counts"]["VISUAL_CHANGES_REQUESTED"] == 0
    assert body["total"] == 3


def test_pipeline_for_empty_brand_is_all_zero(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))

    response = client.get(
        f"/api/v1/creative-items/pipeline?brand_id={workspace['brand_id']}",
        headers=auth_header(workspace["tokens"][BrandRole.CREATOR]),
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body["counts"]) == ALL_STATUSES
    assert all(count == 0 for count in body["counts"].values())
    assert body["total"] == 0


def test_pipeline_any_brand_role_may_read(client: TestClient, session: Session):
    workspace = make_workspace(session)
    create_item(client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"])

    for role in (BrandRole.CREATOR, BrandRole.CONTENT_REVIEWER, BrandRole.VISUAL_REVIEWER):
        response = client.get(
            f"/api/v1/creative-items/pipeline?brand_id={workspace['brand_id']}",
            headers=auth_header(workspace["tokens"][role]),
        )
        assert response.status_code == 200
        assert response.json()["counts"]["DRAFT"] == 1


def test_pipeline_requires_membership(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    other = make_workspace(session, roles=(BrandRole.CREATOR,))

    response = client.get(
        f"/api/v1/creative-items/pipeline?brand_id={workspace['brand_id']}",
        headers=auth_header(other["tokens"][BrandRole.CREATOR]),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_pipeline_requires_brand_id(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))

    token = workspace["tokens"][BrandRole.CREATOR]
    response = client.get("/api/v1/creative-items/pipeline", headers=auth_header(token))

    assert response.status_code == 422
