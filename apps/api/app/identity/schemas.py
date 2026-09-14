"""API schemas for the identity module."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

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


class BrandCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
