"""Content Governance: approve/request-changes transitions, guards, idempotency,
queue/detail/history read models (content-governance change, tasks.md 3.1/3.2/5.1)."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.creative.models import WorkflowEvent
from app.db import get_session
from app.governance.models import ContentReview
from app.identity.models import BrandMembership, BrandRole, Profile
from app.main import app
from tests.conftest import (
    auth_header,
    gather_asgi_requests,
    make_concurrency_engine,
    make_session_override,
    make_token,
    make_workspace,
    seed_race_workspace,
    seed_synced_knowledge,
)
from tests.test_creative_items import create_item
from tests.test_creative_submit import submit
from tests.test_creative_versions import output_for, post_version


def approve(client: TestClient, token: str, item_id):
    return client.post(f"/api/v1/content-reviews/{item_id}/approve", headers=auth_header(token))


def request_changes(client: TestClient, token: str, item_id, feedback: str = "Fix the CTA"):
    return client.post(
        f"/api/v1/content-reviews/{item_id}/request-changes",
        headers=auth_header(token),
        json={"feedback": feedback},
    )


def queue(client: TestClient, token: str):
    return client.get("/api/v1/content-reviews/queue", headers=auth_header(token))


def detail(client: TestClient, token: str, item_id):
    return client.get(f"/api/v1/content-reviews/{item_id}", headers=auth_header(token))


def history(client: TestClient, token: str, item_id):
    return client.get(f"/api/v1/content-reviews/{item_id}/history", headers=auth_header(token))


def _stamp_new_events(session: Session, item_id, seen_ids: set[uuid.UUID], clock: list[int]) -> None:
    """Assign the just-created workflow_event(s) for this item a controlled,
    strictly increasing timestamp.

    SQLite's `CURRENT_TIMESTAMP` is second-resolution, so several API calls
    issued back-to-back within one test can tie on `created_at`; the repo's
    "most recent event" queries then tie-break on the event's random UUID,
    which does not track real call order. Postgres's microsecond `now()`
    doesn't have this problem — this is a test-only stand-in for real elapsed
    time between calls, not a product bug, so it stays in the test file.
    """
    rows = list(
        session.scalars(
            select(WorkflowEvent).where(
                WorkflowEvent.creative_item_id == uuid.UUID(str(item_id))
            )
        )
    )
    new_rows = [row for row in rows if row.id not in seen_ids]
    assert new_rows, "expected at least one new workflow_event since the last stamp"
    base = datetime.now(UTC)
    for row in new_rows:
        clock[0] += 1
        row.created_at = base + timedelta(seconds=clock[0])
        seen_ids.add(row.id)
    session.commit()


def _backdate_only_submission(session: Session, item_id, seconds: int) -> None:
    """Push this item's (currently unique) SUBMITTED event `seconds` into the
    past, so cross-item ordering in the same test isn't at the mercy of
    SQLite's second-resolution clock (see `_stamp_new_events`)."""
    event = session.scalars(
        select(WorkflowEvent).where(
            WorkflowEvent.creative_item_id == uuid.UUID(str(item_id)),
            WorkflowEvent.event_type == "SUBMITTED",
        )
    ).one()
    event.created_at = event.created_at - timedelta(seconds=seconds)
    session.commit()


def _submit_a_version(client: TestClient, session: Session, workspace: dict):
    """Seed synced knowledge (once — see `_submit_second_item_version` for a
    second item on the same already-synced workspace) and submit one item."""
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    seed_synced_knowledge(
        session, workspace["brand_id"], workspace["profiles"][BrandRole.CREATOR].id
    )
    return _submit_second_item_version(client, workspace)


def _submit_second_item_version(client: TestClient, workspace: dict):
    """Submit another item on a workspace whose knowledge is already synced."""
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, creator_token, workspace["brand_id"]).json()
    version = post_version(client, creator_token, item["id"], output_for("product_description")).json()
    response = submit(client, creator_token, item["id"], version["id"])
    assert response.status_code == 200
    return item, version


def test_approve_transitions_and_persists_review_and_event(client: TestClient, session: Session):
    workspace = make_workspace(session)
    reviewer_token = workspace["tokens"][BrandRole.CONTENT_REVIEWER]
    item, version = _submit_a_version(client, session, workspace)

    response = approve(client, reviewer_token, item["id"])

    assert response.status_code == 200
    body = response.json()
    assert body["item"]["workflow_status"] == "CONTENT_APPROVED"
    assert body["review"]["decision"] == "APPROVED"
    assert body["review"]["submitted_version_id"] == version["id"]

    reviews = list(
        session.scalars(
            select(ContentReview).where(
                ContentReview.creative_item_id == uuid.UUID(str(item["id"]))
            )
        )
    )
    assert len(reviews) == 1
    events = list(
        session.scalars(
            select(WorkflowEvent).where(
                WorkflowEvent.creative_item_id == uuid.UUID(str(item["id"])),
                WorkflowEvent.event_type == "CONTENT_APPROVED",
            )
        )
    )
    assert len(events) == 1
    assert events[0].actor_id == workspace["profiles"][BrandRole.CONTENT_REVIEWER].id


def test_approve_twice_is_idempotent_no_duplicate_row(client: TestClient, session: Session):
    workspace = make_workspace(session)
    reviewer_token = workspace["tokens"][BrandRole.CONTENT_REVIEWER]
    item, _version = _submit_a_version(client, session, workspace)

    first = approve(client, reviewer_token, item["id"])
    second = approve(client, reviewer_token, item["id"])

    assert first.status_code == second.status_code == 200
    assert first.json()["review"]["id"] == second.json()["review"]["id"]
    reviews = list(
        session.scalars(
            select(ContentReview).where(
                ContentReview.creative_item_id == uuid.UUID(str(item["id"]))
            )
        )
    )
    assert len(reviews) == 1


def test_opposite_decision_after_approve_is_409(client: TestClient, session: Session):
    workspace = make_workspace(session)
    reviewer_token = workspace["tokens"][BrandRole.CONTENT_REVIEWER]
    item, _version = _submit_a_version(client, session, workspace)
    assert approve(client, reviewer_token, item["id"]).status_code == 200

    response = request_changes(client, reviewer_token, item["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_WORKFLOW_TRANSITION"


def test_request_changes_requires_feedback(client: TestClient, session: Session):
    workspace = make_workspace(session)
    reviewer_token = workspace["tokens"][BrandRole.CONTENT_REVIEWER]
    item, _version = _submit_a_version(client, session, workspace)

    response = request_changes(client, reviewer_token, item["id"], feedback="")

    assert response.status_code == 422


def test_full_cycle_request_changes_resubmit_approve(client: TestClient, session: Session):
    workspace = make_workspace(session)
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    reviewer_token = workspace["tokens"][BrandRole.CONTENT_REVIEWER]
    item, v2 = _submit_a_version(client, session, workspace)
    seen_events: set[uuid.UUID] = set()
    clock = [0]
    _stamp_new_events(session, item["id"], seen_events, clock)  # the v2 SUBMITTED event

    changes = request_changes(client, reviewer_token, item["id"], feedback="Tighten the hook")
    assert changes.status_code == 200
    assert changes.json()["item"]["workflow_status"] == "CONTENT_CHANGES_REQUESTED"
    _stamp_new_events(session, item["id"], seen_events, clock)

    v3 = post_version(client, creator_token, item["id"], output_for("product_description")).json()
    assert submit(client, creator_token, item["id"], v3["id"]).status_code == 200
    _stamp_new_events(session, item["id"], seen_events, clock)  # the v3 SUBMITTED event

    approved = approve(client, reviewer_token, item["id"])
    assert approved.status_code == 200
    assert approved.json()["review"]["submitted_version_id"] == v3["id"]
    _stamp_new_events(session, item["id"], seen_events, clock)

    history_response = history(client, reviewer_token, item["id"])
    types = [e["event_type"] for e in history_response.json()["events"]]
    assert types == ["SUBMITTED", "CONTENT_CHANGES_REQUESTED", "SUBMITTED", "CONTENT_APPROVED"]
    # Append-only + ASC: timestamps never decrease.
    timestamps = [e["created_at"] for e in history_response.json()["events"]]
    assert timestamps == sorted(timestamps)


def test_creator_cannot_approve_or_request_changes(client: TestClient, session: Session):
    workspace = make_workspace(session)
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    item, _version = _submit_a_version(client, session, workspace)

    assert approve(client, creator_token, item["id"]).status_code == 403
    assert request_changes(client, creator_token, item["id"]).status_code == 403


def test_visual_reviewer_cannot_decide(client: TestClient, session: Session):
    workspace = make_workspace(session)
    visual_token = workspace["tokens"][BrandRole.VISUAL_REVIEWER]
    item, _version = _submit_a_version(client, session, workspace)

    response = approve(client, visual_token, item["id"])

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_approve_never_submitted_item_is_409(client: TestClient, session: Session):
    workspace = make_workspace(session)
    reviewer_token = workspace["tokens"][BrandRole.CONTENT_REVIEWER]
    item = create_item(
        client, workspace["tokens"][BrandRole.CREATOR], workspace["brand_id"]
    ).json()

    response = approve(client, reviewer_token, item["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_WORKFLOW_TRANSITION"


def test_reviewer_of_another_brand_gets_404(client: TestClient, session: Session):
    workspace = make_workspace(session)
    other = make_workspace(session, roles=(BrandRole.CONTENT_REVIEWER,))
    item, _version = _submit_a_version(client, session, workspace)

    response = approve(client, other["tokens"][BrandRole.CONTENT_REVIEWER], item["id"])

    assert response.status_code == 404


def test_queue_lists_only_pending_items_ordered_and_isolated_by_brand(
    client: TestClient, session: Session
):
    workspace_a = make_workspace(session)
    workspace_b = make_workspace(session)
    reviewer_a = workspace_a["tokens"][BrandRole.CONTENT_REVIEWER]

    item1, _ = _submit_a_version(client, session, workspace_a)
    _backdate_only_submission(session, item1["id"], seconds=5)  # force item1 before item2 (see helper)
    item2, _ = _submit_second_item_version(client, workspace_a)
    _submit_a_version(client, session, workspace_b)  # different brand: never visible to reviewer_a

    response = queue(client, reviewer_a)

    assert response.status_code == 200
    ids = [row["item"]["id"] for row in response.json()["items"]]
    assert ids == [item1["id"], item2["id"]]  # oldest submission first

    # Approving removes the item from the queue.
    assert approve(client, reviewer_a, item1["id"]).status_code == 200
    remaining = [row["item"]["id"] for row in queue(client, reviewer_a).json()["items"]]
    assert remaining == [item2["id"]]


def test_detail_shows_frozen_version_context_and_latest_feedback(
    client: TestClient, session: Session
):
    workspace = make_workspace(session)
    reviewer_token = workspace["tokens"][BrandRole.CONTENT_REVIEWER]
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    item, v2 = _submit_a_version(client, session, workspace)

    before_decision = detail(client, creator_token, item["id"])
    assert before_decision.status_code == 200
    assert before_decision.json()["submitted_version"]["id"] == v2["id"]
    assert before_decision.json()["latest_review"] is None

    assert request_changes(client, reviewer_token, item["id"], feedback="Tighten it up").status_code == 200

    after_decision = detail(client, creator_token, item["id"])
    body = after_decision.json()
    assert body["latest_review"]["decision"] == "CHANGES_REQUESTED"
    assert body["latest_review"]["feedback"] == "Tighten it up"
    assert body["applied_context"]["version_id"] == v2["id"]
    # The submitted version's content stays exactly as it was when frozen.
    assert body["submitted_version"]["output"]["content"] == "Bites full of real quinoa."


def test_detail_before_any_submission_returns_nulls_not_404(client: TestClient, session: Session):
    workspace = make_workspace(session)
    creator_token = workspace["tokens"][BrandRole.CREATOR]
    item = create_item(client, creator_token, workspace["brand_id"]).json()

    response = detail(client, creator_token, item["id"])

    assert response.status_code == 200
    body = response.json()
    assert body["submitted_version"] is None
    assert body["applied_context"] is None
    assert body["latest_review"] is None


def test_concurrent_approve_never_duplicates_the_decision(tmp_path):
    engine = make_concurrency_engine(tmp_path)
    brand_id, creator_token = seed_race_workspace(engine)

    with Session(engine) as seed_session:
        reviewer = Profile(id=uuid.uuid4(), email=f"reviewer-{uuid.uuid4().hex[:6]}@example.com")
        seed_session.add(reviewer)
        seed_session.add(
            BrandMembership(
                id=uuid.uuid4(),
                profile_id=reviewer.id,
                brand_id=brand_id,
                role=BrandRole.CONTENT_REVIEWER,
            )
        )
        seed_session.commit()
        reviewer_token = make_token(sub=str(reviewer.id), email=reviewer.email)

    app.dependency_overrides[get_session] = make_session_override(engine)
    try:
        with TestClient(app) as setup_client:
            item = create_item(setup_client, creator_token, brand_id).json()
            with Session(engine) as seed_session:
                seed_synced_knowledge(seed_session, brand_id, uuid.UUID(str(item["created_by"])))
            version = post_version(
                setup_client, creator_token, item["id"], output_for("product_description")
            ).json()
            submit_response = submit(setup_client, creator_token, item["id"], version["id"])
            assert submit_response.status_code == 200, submit_response.text

        responses = asyncio.run(
            gather_asgi_requests(
                [
                    {
                        "method": "POST",
                        "url": f"/api/v1/content-reviews/{item['id']}/approve",
                        "headers": auth_header(reviewer_token),
                    }
                ]
                * 3
            )
        )
    finally:
        app.dependency_overrides.clear()

    assert {response.status_code for response in responses} == {200}
    review_ids = {response.json()["review"]["id"] for response in responses}
    assert len(review_ids) == 1
    with Session(engine) as check_session:
        reviews = list(
            check_session.scalars(
                select(ContentReview).where(
                    ContentReview.creative_item_id == uuid.UUID(str(item["id"]))
                )
            )
        )
        assert len(reviews) == 1
