"""Application service for brand_assets: slot-vs-collection upload, replace,
list and delete, all backed by `private-storage` (008) via `StoragePort`.

Guard shape (design.md, mirrors `app.creative.service.create_item` /
`_resolve_item`): upload and list are keyed by `brand_id` from the URL with no
existing resource to protect, so membership+role are checked directly and a
non-member gets 403. Delete is keyed by an existing `asset_id`, so the asset
is resolved first and a missing/foreign/non-member case all answer 404
uniformly; only a member with the wrong role reaches `policies.require_writer`
and gets 403.

Replace semantics (design.md D1): uploading a `PRIMARY_LOGO`/`ALT_LOGO` that
already exists deletes the old row and inserts the new one in the same
transaction (never an in-place `UPDATE storage_path`). The new object is
uploaded to storage before the transaction opens (same provider-safety shape
as `app.visual_audit.service.upload`); a transaction failure triggers
best-effort compensation removing the newly uploaded object, and a successful
replace triggers best-effort compensation removing the now-orphaned old
object -- storage never ends up with two objects for one slot, and the row
never outlives its object or vice versa.
"""

import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.brand_assets import policies, repository
from app.brand_assets.models import SINGLE_SLOT_TYPES, BrandAsset, BrandAssetType
from app.brand_assets.schemas import BrandAssetList, BrandAssetOut
from app.config import Settings
from app.identity.auth import AuthenticatedUser
from app.storage import validation
from app.storage.errors import StorageNotConfiguredError
from app.storage.ports import StoragePort

logger = logging.getLogger(__name__)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand asset not found")


def _asset_path(
    brand_id: uuid.UUID, asset_type: BrandAssetType, asset_id: uuid.UUID, extension: str
) -> str:
    return f"brands/{brand_id}/brand-assets/{asset_type.value.lower()}/{asset_id}{extension}"


def _to_out(asset: BrandAsset, signed_url: str) -> BrandAssetOut:
    return BrandAssetOut(
        id=asset.id,
        brand_id=asset.brand_id,
        brand_dna_version_id=asset.brand_dna_version_id,
        type=asset.type,
        signed_url=signed_url,
        metadata=asset.asset_metadata,
        created_at=asset.created_at,
    )


async def _best_effort_remove(storage: StoragePort, path: str) -> None:
    """Never let a storage cleanup failure surface to the caller (mirrors
    `app.visual_audit.service._compensate_remove`); a stray object is logged,
    not raised, once the row-level invariant it protected has already been
    decided (transaction committed or rolled back)."""
    try:
        await storage.remove_object(path=path)
    except Exception as exc:
        logger.warning(
            "Storage cleanup (remove_object) failed for brand asset: %s", type(exc).__name__
        )


def _insert_asset_locked(
    session: Session,
    brand_id: uuid.UUID,
    *,
    asset_id: uuid.UUID,
    asset_type: BrandAssetType,
    path: str,
    content_type: str,
) -> tuple[BrandAsset, str | None]:
    """Insert under the brand row lock; returns (asset, old_storage_path).

    `old_storage_path` is non-null only when this upload replaced an existing
    single-slot asset (PRIMARY_LOGO/ALT_LOGO) -- the caller compensates by
    removing that object from storage only after this transaction commits.
    """
    if repository.lock_brand(session, brand_id) is None:
        raise _not_found()
    old_path: str | None = None
    if asset_type in SINGLE_SLOT_TYPES:
        existing = repository.get_by_type(session, brand_id, asset_type)
        if existing is not None:
            old_path = existing.storage_path
            repository.delete_asset(session, existing)
            session.flush()  # frees the partial unique slot before the new row is inserted
    brand_dna_version_id = repository.get_active_brand_dna_version_id(session, brand_id)
    asset = repository.insert_asset(
        session,
        id=asset_id,
        brand_id=brand_id,
        brand_dna_version_id=brand_dna_version_id,
        type=asset_type,
        storage_path=path,
        metadata={"content_type": content_type},
    )
    session.flush()
    return asset, old_path


async def upload(
    session: Session,
    user: AuthenticatedUser,
    brand_id: uuid.UUID,
    *,
    asset_type: BrandAssetType,
    content: bytes,
    storage: StoragePort | None,
    settings: Settings,
) -> BrandAssetOut:
    """Upload (or replace, for PRIMARY_LOGO/ALT_LOGO) a brand asset.

    No existing resource to protect (design.md): membership+role are checked
    directly against the URL's `brand_id`, so a non-member gets 403 with no
    existence leak to guard.
    """
    membership = repository.get_membership(session, user.id, brand_id)
    policies.require_writer(membership)
    if storage is None:
        raise StorageNotConfiguredError("brand_assets.upload")
    validated = validation.validate_upload(content, max_bytes=settings.storage_max_upload_bytes)

    asset_id = uuid.uuid4()
    path = _asset_path(brand_id, asset_type, asset_id, validated.extension)
    await storage.put_object(path=path, content=content, content_type=validated.content_type)
    old_path: str | None
    try:
        asset, old_path = _insert_asset_locked(
            session,
            brand_id,
            asset_id=asset_id,
            asset_type=asset_type,
            path=path,
            content_type=validated.content_type,
        )
        session.commit()
    except IntegrityError:
        # Race escaped the lock (partial unique slot index): both racers'
        # objects are already uploaded to distinct paths (fresh uuid4 each),
        # so this object is never orphaned -- only the DB write lost the
        # race. Rollback and retry once under a fresh lock read, which
        # re-resolves `existing` against the winner's now-committed row and
        # deletes it before inserting this one (same single-retry shape as
        # `app.visual_audit.service.upload`).
        session.rollback()
        asset, old_path = _insert_asset_locked(
            session,
            brand_id,
            asset_id=asset_id,
            asset_type=asset_type,
            path=path,
            content_type=validated.content_type,
        )
        session.commit()
    except Exception:
        session.rollback()
        await _best_effort_remove(storage, path)
        raise

    if old_path is not None:
        # The DB transaction already committed the replace; the old object is
        # now unreferenced by any row. Best-effort cleanup, never blocking.
        await _best_effort_remove(storage, old_path)

    signed = await storage.signed_url(
        path=asset.storage_path, ttl_seconds=settings.storage_signed_url_ttl_seconds
    )
    return _to_out(asset, signed)


async def list_assets(
    session: Session,
    user: AuthenticatedUser,
    brand_id: uuid.UUID,
    *,
    storage: StoragePort | None,
    settings: Settings,
) -> BrandAssetList:
    """List a brand's assets. Any member with membership may read (design.md);
    a non-member gets 403 -- no existence leak to guard here either."""
    membership = repository.get_membership(session, user.id, brand_id)
    policies.require_reader(membership)
    assets = repository.list_assets(session, brand_id)
    if assets and storage is None:
        # An empty list never needs storage; only a real asset does.
        raise StorageNotConfiguredError("brand_assets.list")
    out = []
    for asset in assets:
        assert storage is not None  # guarded above whenever assets is non-empty
        signed = await storage.signed_url(
            path=asset.storage_path, ttl_seconds=settings.storage_signed_url_ttl_seconds
        )
        out.append(_to_out(asset, signed))
    return BrandAssetList(assets=out)


async def delete(
    session: Session,
    user: AuthenticatedUser,
    brand_id: uuid.UUID,
    asset_id: uuid.UUID,
    *,
    storage: StoragePort | None,
) -> None:
    """Delete one brand asset. 404 for missing/foreign/non-member (design.md,
    mirrors `_resolve_asset`/`_resolve_item` precedent); a member with the
    wrong role reaches `require_writer` and gets 403."""
    asset = repository.get_asset(session, asset_id)
    if asset is None or asset.brand_id != brand_id:
        raise _not_found()
    membership = repository.get_membership(session, user.id, asset.brand_id)
    if membership is None:
        raise _not_found()
    policies.require_writer(membership)
    if storage is None:
        raise StorageNotConfiguredError("brand_assets.delete")

    path = asset.storage_path
    repository.delete_asset(session, asset)
    session.commit()
    await _best_effort_remove(storage, path)


async def get_primary_logo(
    session: Session,
    brand_id: uuid.UUID,
    *,
    storage: StoragePort | None,
    settings: Settings,
) -> BrandAssetOut | None:
    """Read-only resolution of a brand's PRIMARY_LOGO for cross-module
    consumption (design.md task 3.1 -- `visual-compliance`'s audit flow reads
    through this same path instead of reimplementing storage access).

    No membership check here: the caller (e.g. `app.visual_audit.service.
    run_audit`) has already authorized its own action for this brand; this is
    an internal read, not a new HTTP-reachable surface. Returns `None` when
    the brand has no PRIMARY_LOGO yet -- never touches storage in that case.
    """
    asset = repository.get_by_type(session, brand_id, BrandAssetType.PRIMARY_LOGO)
    if asset is None:
        return None
    if storage is None:
        raise StorageNotConfiguredError("brand_assets.get_primary_logo")
    signed = await storage.signed_url(
        path=asset.storage_path, ttl_seconds=settings.storage_signed_url_ttl_seconds
    )
    return _to_out(asset, signed)
