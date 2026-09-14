"""Recent Activity feed (change 014): merges `workflow_events` with one
synthetic event per published Brand DNA version, descending order, pagination
`limit` (1-50 default 20) + `offset` + `total`, membership-first 403.

Seeds the read model directly (workflow events + a published version row)
instead of exercising every write path end to end — the same shortcut
`tests/test_trace_facade.py` takes for the observability facade, since this
module only reads two tables it does not own the writes for.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.brand_dna.models import BrandDnaStatus, BrandDnaVersion, KnowledgeStatus
from app.creative.models import (
    CreativeItem,
    CreativeItemType,
    CreativeWorkflowStatus,
    WorkflowEvent,
)
from app.identity.models import BrandRole
from tests.conftest import auth_header, make_workspace, valid_document


def _seed_item(session: Session, brand_id: uuid.UUID, created_by: uuid.UUID) -> CreativeItem:
    item = CreativeItem(
        id=uuid.uuid4(),
        brand_id=brand_id,
        type=CreativeItemType.PRODUCT_DESCRIPTION,
        title="Item",
        workflow_status=CreativeWorkflowStatus.DRAFT,
        created_by=created_by,
    )
    session.add(item)
    session.flush()
    return item


def _seed_event(
    session: Session,
    item_id: uuid.UUID,
    event_type: str,
    actor_id: uuid.UUID,
    created_at: datetime,
    metadata: dict | None = None,
) -> WorkflowEvent:
    event = WorkflowEvent(
        id=uuid.uuid4(),
        creative_item_id=item_id,
        event_type=event_type,
        actor_id=actor_id,
        event_metadata=metadata or {},
        created_at=created_at,
    )
    session.add(event)
    return event


def _seed_published_version(
    session: Session,
    brand_id: uuid.UUID,
    created_by: uuid.UUID,
    version: int,
    published_at: datetime,
) -> BrandDnaVersion:
    row = BrandDnaVersion(
        id=uuid.uuid4(),
        brand_id=brand_id,
        version=version,
        # ARCHIVED avoids the one-ACTIVE-per-brand partial unique index so
        # several published rows can coexist in one test.
        status=BrandDnaStatus.ARCHIVED,
        document=valid_document(),
        created_by=created_by,
        knowledge_status=KnowledgeStatus.NOT_SYNCED,
        published_at=published_at,
    )
    session.add(row)
    return row


def test_activity_merges_events_and_publications_in_descending_order(
    client: TestClient, session: Session
):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    creator = workspace["profiles"][BrandRole.CREATOR]
    brand_id = workspace["brand_id"]
    token = workspace["tokens"][BrandRole.CREATOR]

    item = _seed_item(session, brand_id, creator.id)
    now = datetime.now(UTC)
    _seed_event(session, item.id, "SUBMITTED", creator.id, now - timedelta(minutes=1))
    _seed_published_version(session, brand_id, creator.id, 1, now - timedelta(minutes=2))
    session.commit()

    response = client.get(f"/api/v1/activity?brand_id={brand_id}", headers=auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["source"] for item in body["items"]] == ["WORKFLOW_EVENT", "BRAND_DNA_PUBLISHED"]
    assert body["items"][0]["event_type"] == "SUBMITTED"
    assert body["items"][0]["creative_item_id"] == str(item.id)
    assert body["items"][1]["event_type"] == "PUBLISHED"
    assert body["items"][1]["metadata"] == {"version": 1}
    timestamps = [entry["created_at"] for entry in body["items"]]
    assert timestamps == sorted(timestamps, reverse=True)


def test_activity_pagination_matches_facade_shape(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    creator = workspace["profiles"][BrandRole.CREATOR]
    brand_id = workspace["brand_id"]
    token = workspace["tokens"][BrandRole.CREATOR]
    item = _seed_item(session, brand_id, creator.id)

    now = datetime.now(UTC)
    for i in range(5):
        _seed_event(session, item.id, f"EVENT_{i}", creator.id, now - timedelta(minutes=i))
    session.commit()

    base = client.get(f"/api/v1/activity?brand_id={brand_id}", headers=auth_header(token))
    assert base.status_code == 200 and base.json()["total"] == 5
    assert len(base.json()["items"]) == 5  # default limit (20) covers all 5

    page_one = client.get(
        f"/api/v1/activity?brand_id={brand_id}&limit=2", headers=auth_header(token)
    )
    assert page_one.json()["total"] == 5
    assert len(page_one.json()["items"]) == 2
    assert page_one.json()["items"][0]["event_type"] == "EVENT_0"

    page_two = client.get(
        f"/api/v1/activity?brand_id={brand_id}&limit=2&offset=2", headers=auth_header(token)
    )
    assert page_two.json()["items"][0]["event_type"] == "EVENT_2"
    assert page_one.json()["items"] != page_two.json()["items"]

    over_limit = client.get(
        f"/api/v1/activity?brand_id={brand_id}&limit=51", headers=auth_header(token)
    )
    assert over_limit.status_code == 422

    under_limit = client.get(
        f"/api/v1/activity?brand_id={brand_id}&limit=0", headers=auth_header(token)
    )
    assert under_limit.status_code == 422


def test_activity_requires_brand_id(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    response = client.get(
        "/api/v1/activity", headers=auth_header(workspace["tokens"][BrandRole.CREATOR])
    )
    assert response.status_code == 422


def test_activity_requires_membership(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))
    other = make_workspace(session, roles=(BrandRole.CREATOR,))

    response = client.get(
        f"/api/v1/activity?brand_id={workspace['brand_id']}",
        headers=auth_header(other["tokens"][BrandRole.CREATOR]),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_activity_empty_brand_returns_empty_feed(client: TestClient, session: Session):
    workspace = make_workspace(session, roles=(BrandRole.CREATOR,))

    response = client.get(
        f"/api/v1/activity?brand_id={workspace['brand_id']}",
        headers=auth_header(workspace["tokens"][BrandRole.CREATOR]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"items": [], "total": 0}


def test_activity_any_brand_role_may_read(client: TestClient, session: Session):
    workspace = make_workspace(session)
    creator = workspace["profiles"][BrandRole.CREATOR]
    item = _seed_item(session, workspace["brand_id"], creator.id)
    _seed_event(session, item.id, "SUBMITTED", creator.id, datetime.now(UTC))
    session.commit()

    for role in (BrandRole.CREATOR, BrandRole.CONTENT_REVIEWER, BrandRole.VISUAL_REVIEWER):
        response = client.get(
            f"/api/v1/activity?brand_id={workspace['brand_id']}",
            headers=auth_header(workspace["tokens"][role]),
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1
