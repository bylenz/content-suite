"""Draft upsert semantics: single draft, locked writes, OUTDATED transition, concurrency."""

import asyncio

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


def patch(client: TestClient, token: str, brand_id, document=None):
    return client.patch(
        f"/api/v1/brands/{brand_id}/brand-dna/draft",
        headers=auth_header(token),
        json={"document": document or valid_document()},
    )


def version_rows(session: Session, brand_id) -> list[BrandDnaVersion]:
    return list(
        session.scalars(select(BrandDnaVersion).where(BrandDnaVersion.brand_id == brand_id))
    )


def test_first_edit_without_versions_creates_draft_v1(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    creator = workspace["profiles"][BrandRole.CREATOR]

    response = patch(client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"])

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["status"] == "DRAFT"
    assert body["knowledge_status"] == "NOT_SYNCED"
    assert body["created_by"] == str(creator.id)
    assert body["document"]["identity"]["purpose"]


def test_edit_over_active_creates_next_draft_without_touching_active(
    client: TestClient, session: Session
):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    active = create_and_publish(client, workspace)
    session.expire_all()

    response = patch(client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"])

    assert response.status_code == 200
    assert response.json()["version"] == 2
    rows = version_rows(session, workspace["brand_id"])
    assert len(rows) == 2
    active_row = next(r for r in rows if r.status == BrandDnaStatus.ACTIVE)
    assert active_row.document == active["document"]  # immutable
    assert active_row.version == 1


def test_existing_draft_is_updated_in_place(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    first = patch(client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"]).json()
    changed = valid_document()
    changed["identity"]["purpose"] = "Updated purpose"

    second = patch(
        client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"], changed
    ).json()

    assert second["id"] == first["id"]
    assert second["version"] == 1
    assert len(version_rows(session, workspace["brand_id"])) == 1
    assert second["document"]["identity"]["purpose"] == "Updated purpose"


def test_draft_edit_marks_synced_active_as_outdated_once(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    create_and_publish(client, workspace)
    session.expire_all()
    # Only the Knowledge capability can produce SYNCED; simulate its outcome directly.
    active_row = next(
        r for r in version_rows(session, workspace["brand_id"]) if r.status == BrandDnaStatus.ACTIVE
    )
    active_row.knowledge_status = KnowledgeStatus.SYNCED
    session.commit()

    patch(client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"])
    session.expire_all()
    active_row = next(
        r for r in version_rows(session, workspace["brand_id"]) if r.status == BrandDnaStatus.ACTIVE
    )
    assert active_row.knowledge_status == KnowledgeStatus.OUTDATED

    # Idempotent: editing the draft again keeps OUTDATED (no further transitions).
    patch(client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"])
    session.expire_all()
    active_row = next(
        r for r in version_rows(session, workspace["brand_id"]) if r.status == BrandDnaStatus.ACTIVE
    )
    assert active_row.knowledge_status == KnowledgeStatus.OUTDATED


def test_draft_edit_does_not_change_other_knowledge_states(client: TestClient, session: Session):
    for state in (KnowledgeStatus.NOT_SYNCED, KnowledgeStatus.OUTDATED, KnowledgeStatus.FAILED):
        workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
        create_and_publish(client, workspace)
        session.expire_all()
        active_row = next(
            r
            for r in version_rows(session, workspace["brand_id"])
            if r.status == BrandDnaStatus.ACTIVE
        )
        active_row.knowledge_status = state
        session.commit()

        patch(client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"])
        session.expire_all()
        active_row = next(
            r
            for r in version_rows(session, workspace["brand_id"])
            if r.status == BrandDnaStatus.ACTIVE
        )
        assert active_row.knowledge_status == state


def test_reviewer_cannot_write_draft(client: TestClient, session: Session):
    workspace = make_workspace(session)
    create_and_publish(client, workspace)

    for role in (BrandRole.CONTENT_REVIEWER, BrandRole.VISUAL_REVIEWER):
        response = patch(client, workspace["tokens"][role], workspace["brand_id"])
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_write_without_membership_is_permission_denied(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    outsider = make_workspace(session, roles=(BrandRole.CREATOR,))

    response = patch(client, outsider["tokens"][BrandRole.CREATOR], workspace["brand_id"])
    assert response.status_code == 403


def test_integrity_error_race_recovers_deterministically(
    client: TestClient, session: Session, monkeypatch
):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    calls = {"count": 0}
    original_flush = brand_dna_service._flush

    def racing_flush(session_arg):
        if calls["count"] == 0:
            calls["count"] += 1
            raise IntegrityError("simulated unique violation", None, Exception("race"))
        original_flush(session_arg)

    monkeypatch.setattr(brand_dna_service, "_flush", racing_flush)

    response = patch(client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"])

    assert response.status_code == 200
    rows = version_rows(session, workspace["brand_id"])
    assert len(rows) == 1
    assert rows[0].status == BrandDnaStatus.DRAFT
    assert rows[0].version == 1


def test_simultaneous_draft_writes_leave_single_draft(tmp_path):
    engine = make_concurrency_engine(tmp_path)
    brand_id, token = seed_race_workspace(engine)
    document_a = valid_document()
    document_a["identity"]["purpose"] = "Writer A"
    document_b = valid_document()
    document_b["identity"]["purpose"] = "Writer B"

    app.dependency_overrides[get_session] = make_session_override(engine)
    try:
        responses = asyncio.run(
            gather_asgi_requests(
                [
                    {
                        "method": "PATCH",
                        "url": f"/api/v1/brands/{brand_id}/brand-dna/draft",
                        "headers": auth_header(token),
                        "json": {"document": document_a},
                    },
                    {
                        "method": "PATCH",
                        "url": f"/api/v1/brands/{brand_id}/brand-dna/draft",
                        "headers": auth_header(token),
                        "json": {"document": document_b},
                    },
                ]
            )
        )
    finally:
        app.dependency_overrides.clear()

    assert {response.status_code for response in responses} == {200}
    with Session(engine) as check_session:
        rows = list(
            check_session.scalars(
                select(BrandDnaVersion).where(BrandDnaVersion.brand_id == brand_id)
            )
        )
        drafts = [row for row in rows if row.status == BrandDnaStatus.DRAFT]
        assert len(rows) == 1
        assert len(drafts) == 1
        assert rows[0].version == 1
        assert rows[0].document["identity"]["purpose"] in {"Writer A", "Writer B"}
    engine.dispose()
