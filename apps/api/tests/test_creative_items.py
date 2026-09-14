"""Creative item creation and reads: role gates, cross-brand 404, listing scope."""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.identity.models import BrandRole
from tests.conftest import auth_header, make_workspace


def create_item(
    client: TestClient,
    token: str,
    brand_id,
    item_type: str = "PRODUCT_DESCRIPTION",
    title: str = "Quinoa Bites launch",
    brief: dict[str, Any] | None = None,
):
    body: dict[str, Any] = {"brand_id": str(brand_id), "type": item_type, "title": title}
    if brief is not None:
        body["brief"] = brief
    return client.post("/api/v1/creative-items", headers=auth_header(token), json=body)


@pytest.mark.parametrize("item_type", ["PRODUCT_DESCRIPTION", "VIDEO_SCRIPT", "IMAGE_PROMPT"])
def test_creator_creates_draft_item_per_type(client: TestClient, session: Session, item_type):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    creator = workspace["profiles"][BrandRole.CREATOR]

    response = create_item(
        client,
        workspace["tokens"][BrandRole.CREATOR],
        workspace["brand_id"],
        item_type=item_type,
        brief={"goal": "Instagram caption for launch"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["type"] == item_type
    assert body["workflow_status"] == "DRAFT"
    assert body["brand_id"] == str(workspace["brand_id"])
    assert body["created_by"] == str(creator.id)
    assert body["latest_version"] == 1
    # Version 1 carries the brief with no content yet.
    assert body["current_version"]["version"] == 1
    assert body["current_version"]["origin"] == "HUMAN_EDIT"
    assert body["current_version"]["brief"] == {"goal": "Instagram caption for launch"}
    assert body["current_version"]["output"] is None


def test_create_requires_creator_role(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR, BrandRole.CONTENT_REVIEWER))

    response = create_item(
        client, workspace["tokens"][BrandRole.CONTENT_REVIEWER], workspace["brand_id"]
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_create_requires_brand_membership(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    other = make_workspace(session, roles=(BrandRole.CREATOR,))

    response = create_item(
        client, other["tokens"][BrandRole.CREATOR], workspace["brand_id"]
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_create_rejects_unknown_type_and_extra_fields(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]

    bad_type = create_item(client, token, workspace["brand_id"], item_type="BLOG_POST")
    assert bad_type.status_code == 422
    assert bad_type.json()["error"]["code"] == "VALIDATION_ERROR"

    extra = client.post(
        "/api/v1/creative-items",
        headers=auth_header(token),
        json={
            "brand_id": str(workspace["brand_id"]),
            "type": "PRODUCT_DESCRIPTION",
            "title": "T",
            "role": "CREATOR",  # roles are never taken from the client
        },
    )
    assert extra.status_code == 422


def test_create_rejects_brief_over_16kb(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    oversized_brief = {"goal": "x" * (16 * 1024 + 1)}

    response = create_item(client, token, workspace["brand_id"], brief=oversized_brief)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_members_list_and_read_items_of_their_brand(client: TestClient, session: Session):
    workspace = make_workspace(session)
    create_item(client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"])

    for role in (BrandRole.CREATOR, BrandRole.CONTENT_REVIEWER, BrandRole.VISUAL_REVIEWER):
        listed = client.get(
            "/api/v1/creative-items", headers=auth_header(workspace["tokens"][role])
        )
        assert listed.status_code == 200
        items = listed.json()["items"]
        assert len(items) == 1
        assert items[0]["brand_id"] == str(workspace["brand_id"])

        read = client.get(
            f"/api/v1/creative-items/{items[0]['id']}",
            headers=auth_header(workspace["tokens"][role]),
        )
        assert read.status_code == 200
        assert read.json()["id"] == items[0]["id"]


def test_list_with_brand_filter_scopes_to_that_brand(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    other = make_workspace(session, roles=(BrandRole.CREATOR,))
    create_item(client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"])
    create_item(client, other["tokens"][BrandRole.CREATOR], other["brand_id"])

    # A creator of `other` filtering by `workspace.brand_id` has no membership there.
    denied = client.get(
        "/api/v1/creative-items",
        headers=auth_header(other["tokens"][BrandRole.CREATOR]),
        params={"brand_id": str(workspace["brand_id"])},
    )
    assert denied.status_code == 403

    own = client.get(
        "/api/v1/creative-items",
        headers=auth_header(other["tokens"][BrandRole.CREATOR]),
        params={"brand_id": str(other["brand_id"])},
    )
    assert own.status_code == 200
    assert [i["brand_id"] for i in own.json()["items"]] == [str(other["brand_id"])]


def test_cross_brand_item_access_answers_404(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    other = make_workspace(session, roles=(BrandRole.CREATOR,))
    created = create_item(client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"])
    item_id = created.json()["id"]

    for path in ("", "/versions", "/applied-context"):
        response = client.get(
            f"/api/v1/creative-items/{item_id}{path}",
            headers=auth_header(other["tokens"][BrandRole.CREATOR]),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    response = client.post(
        f"/api/v1/creative-items/{item_id}/submit",
        headers=auth_header(other["tokens"][BrandRole.CREATOR]),
        json={"version_id": created.json()["current_version"]["id"]},
    )
    assert response.status_code == 404


def test_missing_item_answers_404(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))

    response = client.get(
        f"/api/v1/creative-items/{uuid.uuid4()}",
        headers=auth_header(workspace["tokens"][BrandRole.CREATOR]),
    )

    assert response.status_code == 404
