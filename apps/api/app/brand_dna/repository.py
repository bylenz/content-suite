"""Repository for Brand DNA version persistence. All SQL lives here."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.brand_dna.models import BrandDnaStatus, BrandDnaVersion
from app.identity import repository as identity_repository
from app.identity.models import Brand, BrandMembership


def get_membership(
    session: Session, profile_id: uuid.UUID, brand_id: uuid.UUID
) -> BrandMembership | None:
    return identity_repository.get_membership(session, profile_id, brand_id)


def lock_brand(session: Session, brand_id: uuid.UUID) -> Brand | None:
    """SELECT ... FOR UPDATE on the brand row; serializes mutations per brand on PostgreSQL."""
    return session.get(Brand, brand_id, with_for_update=True)


def get_draft(session: Session, brand_id: uuid.UUID) -> BrandDnaVersion | None:
    stmt = select(BrandDnaVersion).where(
        BrandDnaVersion.brand_id == brand_id, BrandDnaVersion.status == BrandDnaStatus.DRAFT
    )
    return session.scalars(stmt).first()


def get_active(session: Session, brand_id: uuid.UUID) -> BrandDnaVersion | None:
    stmt = select(BrandDnaVersion).where(
        BrandDnaVersion.brand_id == brand_id, BrandDnaVersion.status == BrandDnaStatus.ACTIVE
    )
    return session.scalars(stmt).first()


def max_version(session: Session, brand_id: uuid.UUID) -> int:
    stmt = select(func.max(BrandDnaVersion.version)).where(BrandDnaVersion.brand_id == brand_id)
    return session.scalar(stmt) or 0


def list_versions(
    session: Session, brand_id: uuid.UUID, include_draft: bool
) -> list[BrandDnaVersion]:
    stmt = select(BrandDnaVersion).where(BrandDnaVersion.brand_id == brand_id)
    if not include_draft:
        stmt = stmt.where(BrandDnaVersion.status != BrandDnaStatus.DRAFT)
    stmt = stmt.order_by(BrandDnaVersion.version.desc())
    return list(session.scalars(stmt))


def get_version(session: Session, brand_id: uuid.UUID, version: int) -> BrandDnaVersion | None:
    stmt = select(BrandDnaVersion).where(
        BrandDnaVersion.brand_id == brand_id, BrandDnaVersion.version == version
    )
    return session.scalars(stmt).first()
