"""Canonical Brand DNA document contract: strict validation, trims, limits, counts."""

import copy

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.brand_dna.schemas import BrandDnaDocument, derive_section_counts
from app.identity.models import BrandRole
from tests.conftest import auth_header, make_workspace, valid_document


def invalid_draft_response(client: TestClient, workspace, document) -> dict:
    """PATCH an invalid document as the workspace CREATOR and return the JSON body."""
    response = client.patch(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/draft",
        headers=auth_header(workspace["tokens"][BrandRole.CREATOR]),
        json={"document": document},
    )
    assert response.status_code == 422
    return response.json()


def validation_details(body: dict) -> list[str]:
    error = body["error"]
    assert error["code"] == "VALIDATION_ERROR"
    return error["details"]["field_errors"]


def test_valid_document_is_accepted_and_trimmed(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    document = valid_document()
    document["identity"]["purpose"] = "  Trimmed purpose  "

    response = client.patch(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/draft",
        headers=auth_header(workspace["tokens"][BrandRole.CREATOR]),
        json={"document": document},
    )

    assert response.status_code == 200
    assert response.json()["document"]["identity"]["purpose"] == "Trimmed purpose"


def test_missing_section_reports_field_path(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    document = valid_document()
    del document["identity"]

    body = invalid_draft_response(client, workspace, document)

    assert "body.document.identity" in validation_details(body)


def test_invalid_type_reports_field_path(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    document = valid_document()
    document["identity"]["personality_traits"] = "Playful"

    body = invalid_draft_response(client, workspace, document)

    assert "body.document.identity.personality_traits" in validation_details(body)


def test_unknown_field_reports_field_path(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    document = valid_document()
    document["identity"]["mood"] = "unexpected"

    body = invalid_draft_response(client, workspace, document)

    assert "body.document.identity.mood" in validation_details(body)


def test_unknown_section_reports_field_path(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    document = valid_document()
    document["extra_section"] = {"rules": ["nope"]}

    body = invalid_draft_response(client, workspace, document)

    assert "body.document.extra_section" in validation_details(body)


def test_empty_string_after_trim_is_invalid(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    document = valid_document()
    document["identity"]["audience"] = "   "

    body = invalid_draft_response(client, workspace, document)

    assert "body.document.identity.audience" in validation_details(body)


def test_cardinality_limit_is_enforced(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    document = valid_document()
    document["identity"]["personality_traits"] = ["Trait"] * 9  # max is 8

    body = invalid_draft_response(client, workspace, document)

    assert "body.document.identity.personality_traits" in validation_details(body)


def test_string_length_limit_is_enforced(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    document = valid_document()
    document["identity"]["purpose"] = "x" * 501  # max is 500

    body = invalid_draft_response(client, workspace, document)

    assert "body.document.identity.purpose" in validation_details(body)


def test_serialized_size_limit_is_enforced(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    document = valid_document()
    # Two list sections at their per-item character limit, filled with 4-byte emoji,
    # exceed the 32 KiB serialized cap while each item stays valid on its own.
    document["restrictions"]["rules"] = ["😀" * 300] * 20
    document["communication"]["rules"] = ["😀" * 300] * 20

    response = client.patch(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/draft",
        headers=auth_header(workspace["tokens"][BrandRole.CREATOR]),
        json={"document": document},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "body.document" in validation_details(response.json())


def test_invalid_document_creates_no_version(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    document = valid_document()
    document["voice"]["do_examples"] = []

    response = client.patch(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/draft",
        headers=auth_header(workspace["tokens"][BrandRole.CREATOR]),
        json={"document": document},
    )

    assert response.status_code == 422
    versions = client.get(
        f"/api/v1/brands/{workspace['brand_id']}/brand-dna/versions",
        headers=auth_header(workspace["tokens"][BrandRole.CREATOR]),
    )
    assert versions.json()["versions"] == []


def test_section_counts_are_derived_deterministically():
    document = BrandDnaDocument.model_validate(valid_document())
    assert derive_section_counts(document) == {
        "identity": 5,  # 3 narratives + 2 traits
        "voice": 7,  # guide + 2 tone characteristics + 3 single-item lists
        "communication": 2,  # 1 pillar + 1 rule
        "visual_rules": 4,  # 4 narratives
        "restrictions": 1,  # 1 rule
    }


def test_document_model_rejects_unknown_keys_and_preserves_contract():
    base = valid_document()
    BrandDnaDocument.model_validate(base)  # contract baseline is valid
    polluted = copy.deepcopy(base)
    polluted["voice"]["preferred_vocabulary"] = ["ok", "  "]
    try:
        BrandDnaDocument.model_validate(polluted)
        raise AssertionError("empty-after-trim list item must be rejected")
    except ValueError:
        pass
