"""Read endpoints and the role visibility matrix (reviewers never see drafts)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.identity.models import BrandRole
from tests.conftest import auth_header, make_workspace, valid_document


def create_and_publish(client: TestClient, workspace) -> dict:
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    brand_id = workspace["brand_id"]
    draft = client.patch(
        f"/api/v1/brands/{brand_id}/brand-dna/draft",
        headers=auth_header(creator_token),
        json={"document": valid_document()},
    ).json()
    return client.post(
        f"/api/v1/brands/{brand_id}/brand-dna/publish",
        headers=auth_header(creator_token),
        json={"expected_draft_id": draft["id"]},
    ).json()


def create_second_draft(client: TestClient, workspace, document=None) -> dict:
    return client.patch(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/draft",
        headers=auth_header(workspace["tokens"][BrandRole.CREATOR]),
        json={"document": document or valid_document()},
    ).json()


def test_member_reads_active_with_document_and_counts(client: TestClient, session: Session):
    workspace = make_workspace(session)
    active = create_and_publish(client, workspace)

    for role in (BrandRole.CREATOR, BrandRole.CONTENT_REVIEWER, BrandRole.VISUAL_REVIEWER):
        response = client.get(
            f"/api/v1/brands/{workspace['brand_id']}/brand-dna",
            headers=auth_header(workspace["tokens"][role]),
        )
        assert response.status_code == 200, role
        body = response.json()
        assert body["active"]["id"] == active["id"]
        assert body["active"]["version"] == 1
        assert body["active"]["document"]["identity"]["purpose"]
        assert body["active"]["section_counts"]["identity"] == 5
        assert body["active"]["knowledge_status"] == "NOT_SYNCED"


def test_reviewers_never_receive_the_draft(client: TestClient, session: Session):
    workspace = make_workspace(session)
    create_and_publish(client, workspace)
    draft = create_second_draft(client, workspace)
    assert draft["status"] == "DRAFT"

    for role in (BrandRole.CONTENT_REVIEWER, BrandRole.VISUAL_REVIEWER):
        overview = client.get(
            f"/api/v1/brands/{workspace['brand_id']}/brand-dna",
            headers=auth_header(workspace["tokens"][role]),
        ).json()
        assert overview["draft"] is None

        versions = client.get(
            f"/api/v1/brands/{workspace['brand_id']}/brand-dna/versions",
            headers=auth_header(workspace["tokens"][role]),
        ).json()["versions"]
        assert all(entry["status"] != "DRAFT" for entry in versions)
        assert all(entry["id"] != draft["id"] for entry in versions)

        detail = client.get(
            f"/api/v1/brands/{workspace['brand_id']}/brand-dna/versions/{draft['version']}",
            headers=auth_header(workspace["tokens"][role]),
        )
        # 404 must not confirm the draft's existence.
        assert detail.status_code == 404
        assert detail.json()["error"]["code"] == "NOT_FOUND"


def test_creator_reads_full_draft(client: TestClient, session: Session):
    workspace = make_workspace(session)
    create_and_publish(client, workspace)
    draft = create_second_draft(client, workspace)

    overview = client.get(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna",
        headers=auth_header(workspace["tokens"][BrandRole.CREATOR]),
    ).json()

    assert overview["draft"]["id"] == draft["id"]
    assert overview["draft"]["status"] == "DRAFT"
    assert overview["draft"]["version"] == 2
    assert overview["draft"]["document"]["identity"]["purpose"]
    assert overview["active"]["id"] != draft["id"]


def test_versions_list_excludes_document_and_orders_desc(client: TestClient, session: Session):
    workspace = make_workspace(session)
    active = create_and_publish(client, workspace)
    create_second_draft(client, workspace)

    response = client.get(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/versions",
        headers=auth_header(workspace["tokens"][BrandRole.CREATOR]),
    )

    versions = response.json()["versions"]
    assert [entry["version"] for entry in versions] == [2, 1]
    for entry in versions:
        assert "document" not in entry
        assert entry["section_counts"]
    assert versions[0]["status"] == "DRAFT"
    assert versions[1]["status"] == "ACTIVE"
    assert versions[1]["id"] == active["id"]


def test_member_reads_published_version_detail_with_full_document(
    client: TestClient, session: Session
):
    workspace = make_workspace(session)
    active = create_and_publish(client, workspace)

    for role in (BrandRole.CREATOR, BrandRole.CONTENT_REVIEWER, BrandRole.VISUAL_REVIEWER):
        detail = client.get(
            f"/api/v1/brands/{workspace['brand_id']}/brand-dna/versions/1",
            headers=auth_header(workspace["tokens"][role]),
        )
        assert detail.status_code == 200, role
        assert detail.json()["id"] == active["id"]
        assert detail.json()["document"]["identity"]["purpose"]


def test_brand_without_published_version_reports_active_null(client: TestClient, session: Session):
    workspace = make_workspace(session)
    create_second_draft(client, workspace)  # only a draft exists

    reviewer_overview = client.get(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna",
        headers=auth_header(workspace["tokens"][BrandRole.CONTENT_REVIEWER]),
    ).json()
    assert reviewer_overview == {"active": None, "draft": None}

    creator_overview = client.get(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna",
        headers=auth_header(workspace["tokens"][BrandRole.CREATOR]),
    ).json()
    assert creator_overview["active"] is None
    assert creator_overview["draft"]["status"] == "DRAFT"


def test_nonexistent_version_is_not_found(client: TestClient, session: Session):
    workspace = make_workspace(session)
    create_and_publish(client, workspace)

    response = client.get(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/versions/99",
        headers=auth_header(workspace["tokens"][BrandRole.CREATOR]),
    )
    assert response.status_code == 404


def test_read_without_membership_is_permission_denied(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    outsider = make_workspace(session, roles=(BrandRole.CONTENT_REVIEWER,))

    for path in ("", "/versions", "/versions/1"):
        response = client.get(
            f"/api/v1/brands/{workspace['brand_id']}/brand-dna{path}",
            headers=auth_header(outsider["tokens"][BrandRole.CONTENT_REVIEWER]),
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_reads_require_authentication(client: TestClient, session: Session):
    workspace = make_workspace(session)

    for path in ("", "/versions", "/versions/1"):
        response = client.get(f"/api/v1/brands/{workspace['brand_id']}/brand-dna{path}")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"

    response = client.patch(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/draft",
        json={"document": valid_document()},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"

    response = client.post(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/publish",
        json={"expected_draft_id": str(workspace["brand_id"])},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
