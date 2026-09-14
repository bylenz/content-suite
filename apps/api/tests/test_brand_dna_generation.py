"""AI generation of the Brand DNA draft from a brief (change 013).

Mirrors `test_creative_ai.py`'s provider-safety tests (503 without a
configured provider; nothing persists on invalid structured output), applied
to `POST /brands/{brand_id}/brand-dna/generate`. All model calls go through
the deterministic `app.ai.fakes.FakeTextModel`: zero network.
"""

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.fakes import FakeTextModel
from app.brand_dna.models import BrandDnaVersion, KnowledgeStatus
from app.brand_dna.router import get_text_adapter, get_tracer_adapter
from app.identity.models import BrandRole
from tests.conftest import auth_header, make_workspace, valid_document
from tests.test_brand_dna_reads import create_and_publish


def valid_brief(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "basics": {
            "brand_name": "Kinu",
            "offering": "Healthy quinoa snack",
            "description": "A snack brand for busy, health-conscious Gen Z consumers",
        },
        "audience": {
            "primary_audience": "Gen Z",
            "market": "Peru",
            "description": "Young consumers looking for healthier and convenient snacks",
            "tags": ["Wellness"],
        },
        "personality": {"traits": ["Playful", "Professional", "Energetic"]},
        "rules": {
            "always": ["Use short and energetic sentences"],
            "never": ["Use technical terminology"],
        },
    }
    payload.update(overrides)
    return payload


def install_adapters(text: Any) -> None:
    """Override the brand_dna router composition roots with test doubles."""
    from app.main import app
    from app.observability.noop import NoopTracer

    app.dependency_overrides[get_text_adapter] = lambda: text
    app.dependency_overrides[get_tracer_adapter] = lambda: NoopTracer()


def generate(client: TestClient, token: str, brand_id, brief: dict[str, Any] | None = None):
    return client.post(
        f"/api/v1/brands/{brand_id}/brand-dna/generate",
        headers=auth_header(token),
        json={"brief": brief if brief is not None else valid_brief()},
    )


def version_rows(session: Session, brand_id) -> list[BrandDnaVersion]:
    return list(
        session.scalars(select(BrandDnaVersion).where(BrandDnaVersion.brand_id == brand_id))
    )


def test_generate_creates_draft_v1_on_brand_without_brand_dna(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    install_adapters(FakeTextModel(structured_output=valid_document()))
    brief = valid_brief()

    response = generate(client, token, workspace["brand_id"], brief)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version"] == 1
    assert body["status"] == "DRAFT"
    assert body["knowledge_status"] == "NOT_SYNCED"
    assert body["document"]["identity"]["purpose"]
    assert body["brief"] == brief
    rows = version_rows(session, workspace["brand_id"])
    assert len(rows) == 1


def test_generate_replaces_existing_draft_in_place(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    install_adapters(FakeTextModel(structured_output=valid_document()))
    first_brief = valid_brief()
    first = generate(client, token, workspace["brand_id"], first_brief).json()

    changed_document = valid_document()
    changed_document["identity"]["purpose"] = "Regenerated purpose"
    install_adapters(FakeTextModel(structured_output=changed_document))
    second_brief = valid_brief(basics={**first_brief["basics"], "brand_name": "Kinu 2"})

    second = generate(client, token, workspace["brand_id"], second_brief).json()

    assert second["id"] == first["id"]
    assert second["version"] == 1  # same DRAFT row, not a new version
    assert second["document"]["identity"]["purpose"] == "Regenerated purpose"
    assert second["brief"] == second_brief
    assert len(version_rows(session, workspace["brand_id"])) == 1


def test_generate_does_not_require_synced_knowledge(client: TestClient, session: Session):
    for state in (KnowledgeStatus.NOT_SYNCED, KnowledgeStatus.OUTDATED, KnowledgeStatus.FAILED):
        workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
        active = create_and_publish(client, workspace)
        active_row = session.get(BrandDnaVersion, uuid.UUID(active["id"]))
        assert active_row is not None
        active_row.knowledge_status = state
        session.commit()
        install_adapters(FakeTextModel(structured_output=valid_document()))

        response = generate(client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"])

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "DRAFT"


def test_generate_marks_synced_active_as_outdated(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    active = create_and_publish(client, workspace)
    active_row = session.get(BrandDnaVersion, uuid.UUID(active["id"]))
    assert active_row is not None
    active_row.knowledge_status = KnowledgeStatus.SYNCED
    session.commit()
    install_adapters(FakeTextModel(structured_output=valid_document()))

    response = generate(client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"])

    assert response.status_code == 200, response.text
    session.expire_all()
    refreshed = session.get(BrandDnaVersion, uuid.UUID(active["id"]))
    assert refreshed is not None
    assert refreshed.knowledge_status == KnowledgeStatus.OUTDATED


def test_generate_503_when_text_provider_unconfigured(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    install_adapters(None)

    response = generate(client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"])

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert version_rows(session, workspace["brand_id"]) == []


def test_generate_with_invalid_structured_output_persists_nothing(
    client: TestClient, session: Session
):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    install_adapters(FakeTextModel(structured_output={"identity": {"purpose": "x"}}))

    response = generate(client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"])

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "AI_OUTPUT_INVALID"
    assert error["details"]["contract"] == "BrandDnaDocument"
    assert version_rows(session, workspace["brand_id"]) == []


def test_generate_invalid_structured_output_does_not_touch_existing_draft(
    client: TestClient, session: Session
):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    install_adapters(FakeTextModel(structured_output=valid_document()))
    before = generate(client, token, workspace["brand_id"]).json()

    install_adapters(FakeTextModel(structured_output={"bogus": True}))
    response = generate(client, token, workspace["brand_id"])

    assert response.status_code == 503
    rows = version_rows(session, workspace["brand_id"])
    assert len(rows) == 1
    assert rows[0].document == before["document"]
    assert rows[0].brief == before["brief"]


def test_reviewer_cannot_generate(client: TestClient, session: Session):
    workspace = make_workspace(session)
    install_adapters(FakeTextModel(structured_output=valid_document()))

    for role in (BrandRole.CONTENT_REVIEWER, BrandRole.VISUAL_REVIEWER):
        response = generate(client, workspace["tokens"][role], workspace["brand_id"])
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_generate_without_membership_is_403(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    outsider = make_workspace(session, roles=(BrandRole.CREATOR,))
    install_adapters(FakeTextModel(structured_output=valid_document()))

    response = generate(client, outsider["tokens"][BrandRole.CREATOR], workspace["brand_id"])

    assert response.status_code == 403


def test_manual_edit_does_not_clear_generated_brief(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    install_adapters(FakeTextModel(structured_output=valid_document()))
    brief = valid_brief()
    generated = generate(client, token, workspace["brand_id"], brief).json()
    assert generated["brief"] == brief

    manual_document = valid_document()
    manual_document["identity"]["purpose"] = "Hand-edited purpose"
    patched = client.patch(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/draft",
        headers=auth_header(token),
        json={"document": manual_document},
    )

    assert patched.status_code == 200
    body = patched.json()
    assert body["document"]["identity"]["purpose"] == "Hand-edited purpose"
    assert body["brief"] == brief  # manual edit never clears a prior generation's brief


def test_generate_rejects_malformed_brief(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    install_adapters(FakeTextModel(structured_output=valid_document()))
    broken = valid_brief()
    broken["rules"]["always"] = []  # violates min_length=1
    token = workspace["tokens"][BrandRole.CREATOR]

    response = generate(client, token, workspace["brand_id"], broken)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_generate_rejects_unknown_brief_field(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    install_adapters(FakeTextModel(structured_output=valid_document()))
    broken = valid_brief()
    broken["extra_field"] = "not allowed"
    token = workspace["tokens"][BrandRole.CREATOR]

    response = generate(client, token, workspace["brand_id"], broken)

    assert response.status_code == 422
