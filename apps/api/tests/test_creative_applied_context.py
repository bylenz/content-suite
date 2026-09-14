"""Applied context: exact Brand DNA version and applied rules of the current version."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.identity.models import BrandRole
from tests.conftest import auth_header, make_workspace
from tests.test_brand_dna_reads import create_and_publish
from tests.test_creative_items import create_item
from tests.test_creative_versions import output_for, post_version


def read_context(client: TestClient, token: str, item_id):
    return client.get(
        f"/api/v1/creative-items/{item_id}/applied-context", headers=auth_header(token)
    )


def test_context_identifies_dna_version_and_rules(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    active = create_and_publish(client, workspace)
    item = create_item(client, token, workspace["brand_id"]).json()

    context = read_context(client, token, item["id"])

    assert context.status_code == 200
    body = context.json()
    assert body["brand_dna_version_id"] == active["id"]
    assert body["applied_rule_ids"] == []
    assert body["version"] == item["current_version"]["version"]
    assert body["version_id"] == item["current_version"]["id"]


def test_context_without_published_dna_has_null_version(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, token, workspace["brand_id"]).json()

    context = read_context(client, token, item["id"])

    assert context.status_code == 200
    assert context.json()["brand_dna_version_id"] is None


def test_context_tracks_the_current_version_after_edit(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    create_and_publish(client, workspace)
    item = create_item(client, token, workspace["brand_id"]).json()
    edited = post_version(client, token, item["id"], output_for("product_description")).json()

    context = read_context(client, token, item["id"])

    assert context.status_code == 200
    assert context.json()["version_id"] == edited["id"]
    assert context.json()["version"] == 2


def test_context_readable_by_reviewers_not_by_other_brand(client: TestClient, session: Session):
    workspace = make_workspace(session)
    other = make_workspace(session, roles=(BrandRole.CREATOR,))
    item = create_item(client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"]).json()

    reviewer = read_context(client, workspace["tokens"][BrandRole.CONTENT_REVIEWER], item["id"])
    assert reviewer.status_code == 200

    foreign = read_context(client, other["tokens"][BrandRole.CREATOR], item["id"])
    assert foreign.status_code == 404
