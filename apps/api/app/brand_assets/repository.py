"""Repository for brand_assets persistence. All SQL lives here.

Reuses `app.brand_dna.repository` for the brand row lock and the ACTIVE Brand
DNA version lookup (both already exist there) instead of duplicating them;
this module's own table is `brand_assets`.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brand_assets.models import BrandAsset, BrandAssetType
from app.brand_dna import repository as brand_dna_repository
from app.identity import repository as identity_repository
from app.identity.models import Brand

# Re-exported so the service module has one import surface for shared tables.
get_membership = identity_repository.get_membership
lock_brand = brand_dna_repository.lock_brand


def get_active_brand_dna_version_id(session: Session, brand_id: uuid.UUID) -> uuid.UUID | None:
    active = brand_dna_repository.get_active(session, brand_id)
    return active.id if active is not None else None


def get_brand(session: Session, brand_id: uuid.UUID) -> Brand | None:
    return session.get(Brand, brand_id)


def get_by_type(
    session: Session, brand_id: uuid.UUID, asset_type: BrandAssetType
) -> BrandAsset | None:
    stmt = select(BrandAsset).where(
        BrandAsset.brand_id == brand_id, BrandAsset.type == asset_type
    )
    return session.scalars(stmt).first()


def list_assets(session: Session, brand_id: uuid.UUID) -> list[BrandAsset]:
    stmt = (
        select(BrandAsset)
        .where(BrandAsset.brand_id == brand_id)
        .order_by(BrandAsset.created_at.desc(), BrandAsset.id.desc())
    )
    return list(session.scalars(stmt))


def get_asset(session: Session, asset_id: uuid.UUID) -> BrandAsset | None:
    return session.get(BrandAsset, asset_id)


def insert_asset(
    session: Session,
    *,
    id: uuid.UUID,
    brand_id: uuid.UUID,
    brand_dna_version_id: uuid.UUID | None,
    type: BrandAssetType,
    storage_path: str,
    metadata: dict,
) -> BrandAsset:
    asset = BrandAsset(
        id=id,
        brand_id=brand_id,
        brand_dna_version_id=brand_dna_version_id,
        type=type,
        storage_path=storage_path,
        asset_metadata=metadata,
    )
    session.add(asset)
    return asset


def delete_asset(session: Session, asset: BrandAsset) -> None:
    session.delete(asset)
