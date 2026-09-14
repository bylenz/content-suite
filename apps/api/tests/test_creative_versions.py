"""Human edit semantics: new immutable version per edit, guards and invariants."""

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.creative.models import CreativeVersion
from app.identity.models import BrandRole
from tests.conftest import auth_header, make_workspace, seed_synced_knowledge
from tests.test_creative_items import create_item


def output_for(item_type: str, title: str = "Quinoa Bites hero", content: str | None = None):
    base: dict[str, Any] = {"content_type": item_type, "title": title, "applied_rule_ids": []}
    if item_type == "video_script":
        base["structured_sections"] = [
            {"heading": "Hook", "body": content or "Crunch into real quinoa."}
        ]
    else:
        base["content"] = content or "Bites full of real quinoa."
    return base


def post_version(
    client: TestClient, token: str, item_id, output: dict, brief: dict | None = None
):
    body: dict[str, Any] = {"output": output}
    if brief is not None:
        body["brief"] = brief
    return client.post(
        f"/api/v1/creative-items/{item_id}/versions", headers=auth_header(token), json=body
    )


def version_rows(session: Session, item_id) -> list[CreativeVersion]:
    return list(
        session.scalars(
            select(CreativeVersion)
            .where(CreativeVersion.creative_item_id == uuid.UUID(str(item_id)))
            .order_by(CreativeVersion.version)
        )
    )


def test_edit_creates_v2_and_v1_stays_intact(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    created = create_item(client, token, workspace["brand_id"], brief={"goal": "launch"}).json()

    response = post_version(client, token, created["id"], output_for("product_description"))

    assert response.status_code == 201
    body = response.json()
    assert body["version"] == 2
    assert body["origin"] == "HUMAN_EDIT"
    # Brief is inherited from the previous version when omitted.
    assert body["brief"] == {"goal": "launch"}
    assert body["output"]["content"] == "Bites full of real quinoa."

    rows = version_rows(session, created["id"])
    assert [r.version for r in rows] == [1, 2]
    assert rows[0].output is None  # v1 untouched
    assert rows[0].brief == {"goal": "launch"}


def test_explicit_brief_replaces_previous(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    created = create_item(client, token, workspace["brand_id"]).json()

    response = post_version(
        client,
        token,
        created["id"],
        output_for("product_description"),
        brief={"goal": "black friday"},
    )

    assert response.status_code == 201
    assert response.json()["brief"] == {"goal": "black friday"}


def test_versions_are_numbered_monotonically(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    created = create_item(client, token, workspace["brand_id"], item_type="VIDEO_SCRIPT").json()

    first = post_version(client, token, created["id"], output_for("video_script")).json()
    second = post_version(
        client,
        token,
        created["id"],
        output_for("video_script", content="Second scene body."),
    ).json()

    assert (first["version"], second["version"]) == (2, 3)
    listed = client.get(
        f"/api/v1/creative-items/{created['id']}/versions", headers=auth_header(token)
    )
    assert listed.status_code == 200
    assert [v["version"] for v in listed.json()["versions"]] == [3, 2, 1]


def test_reviewer_cannot_edit(client: TestClient, session: Session):
    workspace = make_workspace(session)
    reviewer_token = workspace["tokens"][BrandRole.CONTENT_REVIEWER]
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    created = create_item(client, creator_token, workspace["brand_id"]).json()

    response = post_version(
        client, reviewer_token, created["id"], output_for("product_description")
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_edit_by_non_member_is_404(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    other = make_workspace(session, roles=(BrandRole.CREATOR,))
    created = create_item(
        client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"]
    ).json()

    response = post_version(
        client,
        other["tokens"][BrandRole.CREATOR],
        created["id"],
        output_for("product_description"),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_edit_while_pending_review_is_rejected(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    seed_synced_knowledge(
        session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id
    )
    created = create_item(client, token, workspace["brand_id"]).json()
    version = post_version(client, token, created["id"], output_for("product_description")).json()
    submitted = client.post(
        f"/api/v1/creative-items/{created['id']}/submit",
        headers=auth_header(token),
        json={"version_id": version["id"]},
    )
    assert submitted.status_code == 200

    response = post_version(client, token, created["id"], output_for("product_description"))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_WORKFLOW_TRANSITION"


def test_output_content_type_must_match_item_type(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    created = create_item(client, token, workspace["brand_id"], item_type="IMAGE_PROMPT").json()

    response = post_version(client, token, created["id"], output_for("product_description"))

    assert response.status_code == 422


def test_output_contract_rejects_both_and_neither_body(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    created = create_item(client, token, workspace["brand_id"]).json()
    both = output_for("product_description")
    both["structured_sections"] = [{"heading": "H", "body": "B"}]

    for output in (
        both,
        {k: v for k, v in output_for("product_description").items() if k != "content"},
    ):
        response = post_version(client, token, created["id"], output)
        assert response.status_code == 422


def test_version_detail_returns_full_version_for_creator(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    created = create_item(client, token, workspace["brand_id"], brief={"goal": "launch"}).json()
    edited = post_version(
        client,
        token,
        created["id"],
        output_for("product_description"),
        brief={"goal": "black friday"},
    ).json()

    response = client.get(
        f"/api/v1/creative-items/{created['id']}/versions/{edited['id']}",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == edited["id"]
    assert body["version"] == 2
    assert body["origin"] == "HUMAN_EDIT"
    assert body["brief"] == {"goal": "black friday"}
    assert body["output"]["content"] == "Bites full of real quinoa."
    assert body["applied_rule_ids"] == []
    assert body["consistency_score"] is None
    assert body["langfuse_trace_id"] is None
    # v1 (brief-only) is also readable in full.
    listed = client.get(
        f"/api/v1/creative-items/{created['id']}/versions", headers=auth_header(token)
    ).json()
    v1_id = next(v["id"] for v in listed["versions"] if v["version"] == 1)
    first = client.get(
        f"/api/v1/creative-items/{created['id']}/versions/{v1_id}", headers=auth_header(token)
    )
    assert first.status_code == 200
    assert first.json()["output"] is None
    assert first.json()["brief"] == {"goal": "launch"}


def test_version_detail_readable_by_same_brand_reviewer(client: TestClient, session: Session):
    workspace = make_workspace(session)
    reviewer_token = workspace["tokens"][BrandRole.CONTENT_REVIEWER]
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    created = create_item(client, creator_token, workspace["brand_id"]).json()
    edited = post_version(
        client, creator_token, created["id"], output_for("product_description")
    ).json()

    response = client.get(
        f"/api/v1/creative-items/{created['id']}/versions/{edited['id']}",
        headers=auth_header(reviewer_token),
    )

    assert response.status_code == 200
    assert response.json()["output"]["content"].startswith("Bites")


def test_version_detail_non_member_gets_404(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    created = create_item(client, token, workspace["brand_id"]).json()
    edited = post_version(
        client, token, created["id"], output_for("product_description")
    ).json()

    outsider = make_workspace(session, roles=(BrandRole.CREATOR,))
    response = client.get(
        f"/api/v1/creative-items/{created['id']}/versions/{edited['id']}",
        headers=auth_header(outsider["tokens"][BrandRole.CREATOR]),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_version_detail_rejects_version_of_other_item(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    first = create_item(client, token, workspace["brand_id"]).json()
    second = create_item(client, token, workspace["brand_id"]).json()
    edited_second = post_version(
        client, token, second["id"], output_for("product_description")
    ).json()

    response = client.get(
        f"/api/v1/creative-items/{first['id']}/versions/{edited_second['id']}",
        headers=auth_header(token),
    )

    assert response.status_code == 404


def test_image_prompt_uses_content_and_video_script_uses_sections(
    client: TestClient, session: Session
):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]

    video = create_item(client, token, workspace["brand_id"], item_type="VIDEO_SCRIPT").json()
    edited_video = post_version(client, token, video["id"], output_for("video_script"))
    assert edited_video.status_code == 201
    assert edited_video.json()["output"]["structured_sections"][0]["heading"] == "Hook"

    image = create_item(client, token, workspace["brand_id"], item_type="IMAGE_PROMPT").json()
    edited_image = post_version(client, token, image["id"], output_for("image_prompt"))
    assert edited_image.status_code == 201
    assert edited_image.json()["output"]["content"].startswith("Bites")
