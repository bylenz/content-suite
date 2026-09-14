"""Application service for the Recent Activity feed (change 014).

Membership-first (design.md): resolved before any repository read, exactly
like the observability facade. The feed is a merge-at-read of two existing
sources — no new event log table — sorted descending by timestamp and
paginated the same way the facade already does (`limit` 1-50 default 20,
`offset`, real `total`). `brand_id` is always explicit here (unlike the
facade's optional aggregate mode): Dashboard is a single active-workspace
view (`useActiveBrand.ts`), so there is no "all my brands" case to support.
"""

import uuid

from sqlalchemy.orm import Session

from app.activity import policies, repository
from app.activity.schemas import ActivityEventOut, ActivityListResponse, ActivitySource
from app.brand_dna.models import BrandDnaVersion
from app.creative.models import WorkflowEvent
from app.identity.auth import AuthenticatedUser


def _from_workflow_event(event: WorkflowEvent) -> ActivityEventOut:
    return ActivityEventOut(
        id=event.id,
        source=ActivitySource.WORKFLOW_EVENT,
        event_type=event.event_type,
        actor_id=event.actor_id,
        created_at=event.created_at,
        creative_item_id=event.creative_item_id,
        metadata=event.event_metadata,
    )


def _from_published_version(version: BrandDnaVersion) -> ActivityEventOut:
    # `published_at` is guaranteed non-null by the repository query; the
    # actor is the version's author (design.md: "published_at/created_by").
    assert version.published_at is not None
    return ActivityEventOut(
        id=version.id,
        source=ActivitySource.BRAND_DNA_PUBLISHED,
        event_type="PUBLISHED",
        actor_id=version.created_by,
        created_at=version.published_at,
        brand_dna_version_id=version.id,
        metadata={"version": version.version},
    )


def list_activity(
    session: Session,
    user: AuthenticatedUser,
    brand_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
) -> ActivityListResponse:
    membership = repository.get_membership(session, user.id, brand_id)
    policies.require_reader(membership)

    workflow_events = repository.list_workflow_events(session, brand_id)
    published_versions = repository.list_published_brand_dna_versions(session, brand_id)
    merged = [
        *(_from_workflow_event(event) for event in workflow_events),
        *(_from_published_version(version) for version in published_versions),
    ]
    # Descending chronological order; `id` breaks exact-timestamp ties
    # deterministically so pagination never skips or repeats a row.
    merged.sort(key=lambda item: (item.created_at, str(item.id)), reverse=True)
    page = merged[offset : offset + limit]
    return ActivityListResponse(items=page, total=len(merged))
