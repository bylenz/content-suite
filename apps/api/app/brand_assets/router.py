"""Brand Assets router. No SQL here; auth dependency and membership policies
resolve access. Storage arrives as a dependency-injected composition root
(visual_audit-router pattern): `None` is the only unconfigured-storage
representation. No storage SDK is imported in this file.
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.brand_assets import service
from app.brand_assets.models import BrandAssetType
from app.brand_assets.schemas import BrandAssetList, BrandAssetOut
from app.config import Settings, get_settings
from app.db import get_session
from app.identity.auth import AuthenticatedUser, get_current_user
from app.storage.ports import StoragePort
from app.storage.providers import resolve_storage

router = APIRouter(prefix="/brands/{brand_id}/assets", tags=["brand-assets"])


def get_storage_adapter(settings: Settings = Depends(get_settings)) -> StoragePort | None:
    """Compositional root: `None` is the only unconfigured-storage representation."""
    return resolve_storage(settings)


@router.post("", response_model=BrandAssetOut, status_code=status.HTTP_201_CREATED)
async def upload_brand_asset(
    brand_id: uuid.UUID,
    type: BrandAssetType = Form(...),
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    storage: StoragePort | None = Depends(get_storage_adapter),
) -> BrandAssetOut:
    content = await file.read()
    return await service.upload(
        session,
        user,
        brand_id,
        asset_type=type,
        content=content,
        storage=storage,
        settings=settings,
    )


@router.get("", response_model=BrandAssetList)
async def list_brand_assets(
    brand_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    storage: StoragePort | None = Depends(get_storage_adapter),
) -> BrandAssetList:
    return await service.list_assets(session, user, brand_id, storage=storage, settings=settings)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_brand_asset(
    brand_id: uuid.UUID,
    asset_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    storage: StoragePort | None = Depends(get_storage_adapter),
) -> None:
    await service.delete(session, user, brand_id, asset_id, storage=storage)
