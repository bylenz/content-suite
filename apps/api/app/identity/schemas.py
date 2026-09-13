"""API schemas for the identity module."""

import uuid

from pydantic import BaseModel

from app.identity.models import BrandRole


class MembershipOut(BaseModel):
    brand_id: uuid.UUID
    brand_name: str
    brand_slug: str
    role: BrandRole


class Me(BaseModel):
    id: uuid.UUID
    email: str | None
    display_name: str | None
    memberships: list[MembershipOut]
