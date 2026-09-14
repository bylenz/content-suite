"""Submit semantics: transitions, idempotency, freeze invariant and workflow events."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.creative.models import CreativeItem, CreativeVersion, CreativeWorkflowStatus, WorkflowEvent
from app.identity.models import BrandRole
from tests.conftest import auth_header, make_workspace, seed_synced_knowledge
from tests.test_creative_items import create_item
from tests.test_creative_versions import output_for, post_version


def submit(client: TestClient, token: str, item_id, version_id):
    return client.post(
        f"/api/v1/creative-items/{item_id}/submit",
        headers=auth_header(token),
        json={"version_id": str(version_id)},
    )


def force_status(session: Session, item_id, status_: CreativeWorkflowStatus) -> None:
    """Seed a review decision state; governance (phase 5) owns the real transition."""
    session.get(CreativeItem, uuid.UUID(str(item_id))).workflow_status = status_
    session.commit()


def events_for(session: Session, item_id) -> list[WorkflowEvent]:
    return list(
        session.scalars(
            select(WorkflowEvent).where(
                WorkflowEvent.creative_item_id == uuid.UUID(str(item_id))
            )
        )
    )


def test_submit_transitions_to_pending_and_persists_event(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    seed_synced_knowledge(
        session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id
    )
    item = create_item(client, token, workspace["brand_id"]).json()
    version = post_version(client, token, item["id"], output_for("product_description")).json()

    response = submit(client, token, item["id"], version["id"])

    assert response.status_code == 200
    assert response.json()["workflow_status"] == "PENDING_CONTENT_REVIEW"
    events = events_for(session, item["id"])
    assert len(events) == 1
    assert events[0].event_type == "SUBMITTED"
    assert events[0].actor_id == workspace["profiles"][BrandRole.CREATOR].id
    assert events[0].event_metadata["version_id"] == str(version["id"])
    assert events[0].event_metadata["version"] == 2


def test_submit_same_version_twice_is_idempotent(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    seed_synced_knowledge(
        session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id
    )
    item = create_item(client, token, workspace["brand_id"]).json()
    version = post_version(client, token, item["id"], output_for("product_description")).json()

    first = submit(client, token, item["id"], version["id"])
    second = submit(client, token, item["id"], version["id"])

    assert first.status_code == second.status_code == 200
    assert second.json()["workflow_status"] == "PENDING_CONTENT_REVIEW"
    # No duplicate event for the idempotent retry.
    assert len(events_for(session, item["id"])) == 1


def test_submit_different_version_while_pending_is_409(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    seed_synced_knowledge(
        session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id
    )
    item = create_item(client, token, workspace["brand_id"]).json()
    v2 = post_version(client, token, item["id"], output_for("product_description")).json()
    assert submit(client, token, item["id"], v2["id"]).status_code == 200

    # A new version while pending cannot be submitted (and cannot even be created).
    force_status(session, item["id"], CreativeWorkflowStatus.CONTENT_CHANGES_REQUESTED)
    v3 = post_version(client, token, item["id"], output_for("product_description")).json()
    force_status(session, item["id"], CreativeWorkflowStatus.PENDING_CONTENT_REVIEW)
    response = submit(client, token, item["id"], v3["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_WORKFLOW_TRANSITION"


def test_resubmit_after_changes_requested_requires_new_version(
    client: TestClient, session: Session
):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    seed_synced_knowledge(
        session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id
    )
    item = create_item(client, token, workspace["brand_id"]).json()
    v2 = post_version(client, token, item["id"], output_for("product_description")).json()
    assert submit(client, token, item["id"], v2["id"]).status_code == 200

    force_status(session, item["id"], CreativeWorkflowStatus.CONTENT_CHANGES_REQUESTED)
    # The already-submitted v2 cannot be resubmitted.
    stale = submit(client, token, item["id"], v2["id"])
    assert stale.status_code == 409
    assert "already submitted" in stale.json()["error"]["message"]

    v3 = post_version(client, token, item["id"], output_for("product_description")).json()
    response = submit(client, token, item["id"], v3["id"])
    assert response.status_code == 200
    assert response.json()["workflow_status"] == "PENDING_CONTENT_REVIEW"
    # Two SUBMITTED events: v2 and v3.
    assert len(events_for(session, item["id"])) == 2


def test_submitted_version_stays_frozen(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    seed_synced_knowledge(
        session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id
    )
    item = create_item(client, token, workspace["brand_id"]).json()
    v2 = post_version(client, token, item["id"], output_for("product_description")).json()
    assert submit(client, token, item["id"], v2["id"]).status_code == 200

    # Editing is rejected while pending; the submitted row never changes.
    edit = post_version(client, token, item["id"], output_for("product_description"))
    assert edit.status_code == 409
    row = session.scalars(
        select(CreativeVersion).where(CreativeVersion.id == uuid.UUID(v2["id"]))
    ).one()
    assert row.output["content"] == "Bites full of real quinoa."

    force_status(session, item["id"], CreativeWorkflowStatus.CONTENT_CHANGES_REQUESTED)
    v3 = post_version(client, token, item["id"], output_for("product_description")).json()
    assert v3["version"] == 3
    session.expire_all()
    rows = list(
        session.scalars(select(CreativeVersion).where(CreativeVersion.id == uuid.UUID(v2["id"])))
    )
    assert rows[0].output["content"] == "Bites full of real quinoa."


def test_submit_version_of_another_item_is_404(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, token, workspace["brand_id"]).json()
    other = create_item(client, token, workspace["brand_id"], title="Second item").json()
    other_version = post_version(
        client, token, other["id"], output_for("product_description")
    ).json()

    response = submit(client, token, item["id"], other_version["id"])

    assert response.status_code == 404


def test_reviewer_cannot_submit(client: TestClient, session: Session):
    workspace = make_workspace(session)
    reviewer_token = workspace["tokens"][BrandRole.CONTENT_REVIEWER]
    item = create_item(client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"]).json()
    version = post_version(
        client,
        workspace["tokens"][BrandRole.CREATOR],
        item["id"],
        output_for("product_description"),
    ).json()

    response = submit(client, reviewer_token, item["id"], version["id"])

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_submit_from_terminal_states_is_409(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, token, workspace["brand_id"]).json()
    version = post_version(client, token, item["id"], output_for("product_description")).json()

    force_status(session, item["id"], CreativeWorkflowStatus.CONTENT_APPROVED)
    response = submit(client, token, item["id"], version["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_WORKFLOW_TRANSITION"
