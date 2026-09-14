"""Repository for the derived activity feed (change 014). All SQL lives here.

No new table: reads `workflow_events` (scoped to the brand through
`creative_items`, since the event row itself carries no `brand_id`) and
`brand_dna_versions` for its published rows. Both are existing tables owned
by `app.creative` and `app.brand_dna` respectively.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brand_dna.models import BrandDnaVersion
from app.creative.models import CreativeItem, WorkflowEvent
from app.identity import repository as identity_repository
from app.identity.models import BrandMembership


def get_membership(
    session: Session, profile_id: uuid.UUID, brand_id: uuid.UUID
) -> BrandMembership | None:
    return identity_repository.get_membership(session, profile_id, brand_id)


def list_workflow_events(session: Session, brand_id: uuid.UUID) -> Sequence[WorkflowEvent]:
    """Every workflow event for the brand's creative items, unordered (the
    service merges and sorts alongside Brand DNA publications)."""
    stmt = select(WorkflowEvent).join(
        CreativeItem, CreativeItem.id == WorkflowEvent.creative_item_id
    ).where(CreativeItem.brand_id == brand_id)
    return list(session.scalars(stmt))


def list_published_brand_dna_versions(
    session: Session, brand_id: uuid.UUID
) -> Sequence[BrandDnaVersion]:
    """Every Brand DNA version of the brand that was ever published (`published_at`
    non-null), regardless of current status (ACTIVE or since superseded/ARCHIVED)."""
    stmt = select(BrandDnaVersion).where(
        BrandDnaVersion.brand_id == brand_id, BrandDnaVersion.published_at.is_not(None)
    )
    return list(session.scalars(stmt))
