"""Publish semantics: transactional transition, idempotency, conflicts, concurrency."""

import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.brand_dna import service as brand_dna_service
from app.brand_dna.models import BrandDnaStatus, BrandDnaVersion, KnowledgeStatus
from app.db import get_session
from app.identity.models import BrandRole
from app.main import app
from tests.conftest import (
    auth_header,
    gather_asgi_requests,
    make_concurrency_engine,
    make_session_override,
    make_workspace,
    seed_race_workspace,
    valid_document,
)
from tests.test_brand_dna_reads import create_and_publish


def publish(client: TestClient, token: str, brand_id, expected_draft_id):
    response = client.post(
        f"/api/v1/brands/{brand_id}/brand-dna/publish",
        headers=auth_header(token),
        json={"expected_draft_id": expected_draft_id},
    )
    assert response.status_code in (200, 403, 409), response.text
    return response


def version_rows(session: Session, brand_id) -> list[BrandDnaVersion]:
    return list(
        session.scalars(select(BrandDnaVersion).where(BrandDnaVersion.brand_id == brand_id))
    )


def test_first_publish_activates_draft(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    draft = client.patch(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/draft",
        headers=auth_header(creator_token),
        json={"document": valid_document()},
    ).json()

    response = publish(client, creator_token, workspace["brand_id"], draft["id"])

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == draft["id"]  # the draft row itself transitions
    assert body["status"] == "ACTIVE"
    assert body["published_at"] is not None
    assert body["knowledge_status"] == "NOT_SYNCED"


def test_publish_new_version_archives_previous_untouched(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    first_active = create_and_publish(client, workspace)
    session.expire_all()

    draft = client.patch(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/draft",
        headers=auth_header(creator_token),
        json={"document": valid_document()},
    ).json()
    second_active = publish(client, creator_token, workspace["brand_id"], draft["id"]).json()

    session.expire_all()
    rows = version_rows(session, workspace["brand_id"])
    assert {(row.version, row.status) for row in rows} == {(1, "ARCHIVED"), (2, "ACTIVE")}
    archived = next(row for row in rows if row.status == BrandDnaStatus.ARCHIVED)
    assert str(archived.id) == first_active["id"]
    assert archived.document == first_active["document"]  # integrity preserved
    assert archived.published_at is not None

    detail = client.get(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/versions/1",
        headers=auth_header(creator_token),
    )
    assert detail.status_code == 200
    assert detail.json()["document"] == first_active["document"]
    assert second_active["version"] == 2


def test_publish_retry_with_same_expected_draft_id_is_idempotent(
    client: TestClient, session: Session
):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    draft = client.patch(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/draft",
        headers=auth_header(creator_token),
        json={"document": valid_document()},
    ).json()

    first = publish(client, creator_token, workspace["brand_id"], draft["id"])
    retry = publish(client, creator_token, workspace["brand_id"], draft["id"])

    assert retry.status_code == 200
    assert retry.json()["id"] == first.json()["id"]
    assert retry.json()["version"] == 1
    assert len(version_rows(session, workspace["brand_id"])) == 1


def test_publish_with_stale_expected_draft_id_conflicts(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    create_and_publish(client, workspace)
    draft = client.patch(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/draft",
        headers=auth_header(creator_token),
        json={"document": valid_document()},
    ).json()

    stale = publish(client, creator_token, workspace["brand_id"], str(uuid.uuid4()))

    assert stale.status_code == 409
    error = stale.json()["error"]
    assert error["code"] == "INVALID_WORKFLOW_TRANSITION"
    assert error["details"]["expected_draft_id"] != draft["id"]


def test_publish_without_versions_conflicts(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))

    response = publish(
        client,
        workspace["tokens"][BrandRole.CREATOR],
        workspace["brand_id"],
        str(uuid.uuid4()),
    )

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "INVALID_WORKFLOW_TRANSITION"
    assert error["details"]["active_version_id"] is None


def test_publish_without_draft_but_matching_active_is_idempotent(
    client: TestClient, session: Session
):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    active = create_and_publish(client, workspace)

    retry = publish(client, creator_token, workspace["brand_id"], active["id"])

    assert retry.status_code == 200
    assert retry.json()["id"] == active["id"]
    assert len(version_rows(session, workspace["brand_id"])) == 1


def test_reviewer_cannot_publish(client: TestClient, session: Session):
    workspace = make_workspace(session)
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    draft = client.patch(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/draft",
        headers=auth_header(creator_token),
        json={"document": valid_document()},
    ).json()

    for role in (BrandRole.CONTENT_REVIEWER, BrandRole.VISUAL_REVIEWER):
        response = publish(client, workspace["tokens"][role], workspace["brand_id"], draft["id"])
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_publish_missing_required_body_field_is_validation_error(
    client: TestClient, session: Session
):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))

    response = client.post(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/publish",
        headers=auth_header(workspace["tokens"][BrandRole.CREATOR]),
        json={},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "body.expected_draft_id" in response.json()["error"]["details"]["field_errors"]


def test_integrity_error_after_active_archive_recovers_and_publishes(
    client: TestClient, session: Session, monkeypatch
):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    create_and_publish(client, workspace)
    session.expire_all()
    draft = client.patch(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/draft",
        headers=auth_header(creator_token),
        json={"document": valid_document()},
    ).json()
    calls = {"count": 0}
    original_flush = brand_dna_service._flush

    def racing_flush(session_arg):
        if calls["count"] == 0:
            calls["count"] += 1
            raise IntegrityError("simulated partial active index race", None, Exception("race"))
        original_flush(session_arg)

    monkeypatch.setattr(brand_dna_service, "_flush", racing_flush)

    response = publish(client, creator_token, workspace["brand_id"], draft["id"])

    assert response.status_code == 200
    assert response.json()["version"] == 2
    assert response.json()["status"] == "ACTIVE"
    rows = version_rows(session, workspace["brand_id"])
    assert {row.status for row in rows} == {"ARCHIVED", "ACTIVE"}
    assert len([row for row in rows if row.status == BrandDnaStatus.ACTIVE]) == 1


def test_integrity_error_when_already_published_is_idempotent(
    client: TestClient, session: Session, monkeypatch
):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    draft = client.patch(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/draft",
        headers=auth_header(creator_token),
        json={"document": valid_document()},
    ).json()
    original_locked = brand_dna_service._publish_locked

    def publish_then_race(session_arg, brand_id, expected_draft_id):
        original_locked(session_arg, brand_id, expected_draft_id)
        session_arg.commit()  # the racing request already consolidated the transition
        raise IntegrityError("simulated concurrent publish", None, Exception("race"))

    monkeypatch.setattr(brand_dna_service, "_publish_locked", publish_then_race)

    response = publish(client, creator_token, workspace["brand_id"], draft["id"])

    assert response.status_code == 200
    assert response.json()["id"] == draft["id"]
    assert response.json()["status"] == "ACTIVE"
    assert len(version_rows(session, workspace["brand_id"])) == 1


def test_concurrent_publish_of_same_draft_never_duplicates_active(tmp_path):
    engine = make_concurrency_engine(tmp_path)
    brand_id, token = seed_race_workspace(engine)

    app.dependency_overrides[get_session] = make_session_override(engine)
    try:
        draft_response = asyncio.run(
            gather_asgi_requests(
                [
                    {
                        "method": "PATCH",
                        "url": f"/api/v1/brands/{brand_id}/brand-dna/draft",
                        "headers": auth_header(token),
                        "json": {"document": valid_document()},
                    }
                ]
            )
        )[0]
        assert draft_response.status_code == 200, draft_response.text
        draft_id = draft_response.json()["id"]

        responses = asyncio.run(
            gather_asgi_requests(
                [
                    {
                        "method": "POST",
                        "url": f"/api/v1/brands/{brand_id}/brand-dna/publish",
                        "headers": auth_header(token),
                        "json": {"expected_draft_id": draft_id},
                    },
                ]
                * 2
            )
        )
    finally:
        app.dependency_overrides.clear()

    assert {response.status_code for response in responses} == {200}
    ids = {response.json()["id"] for response in responses}
    assert ids == {draft_id}
    with Session(engine) as check_session:
        rows = list(
            check_session.scalars(
                select(BrandDnaVersion).where(BrandDnaVersion.brand_id == brand_id)
            )
        )
        actives = [row for row in rows if row.status == BrandDnaStatus.ACTIVE]
        assert len(rows) == 1
        assert len(actives) == 1
        assert actives[0].knowledge_status == KnowledgeStatus.NOT_SYNCED
        assert actives[0].published_at is not None
    engine.dispose()
