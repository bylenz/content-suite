"""ORM models for identity and RBAC, based on DATA_MODEL.md tables."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class BrandRole(enum.StrEnum):
    CREATOR = "CREATOR"
    CONTENT_REVIEWER = "CONTENT_REVIEWER"
    VISUAL_REVIEWER = "VISUAL_REVIEWER"


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
    display_name: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    name: Mapped[str]
    slug: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    memberships: Mapped[list["BrandMembership"]] = relationship(back_populates="brand")


class BrandMembership(Base):
    __tablename__ = "brand_memberships"
    __table_args__ = (UniqueConstraint("profile_id", "brand_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id"))
    role: Mapped[BrandRole] = mapped_column(Enum(BrandRole, name="brand_role"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    brand: Mapped[Brand] = relationship(back_populates="memberships")
