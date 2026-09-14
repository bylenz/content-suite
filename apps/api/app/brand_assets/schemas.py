"""Schemas for brand_assets: API resources only (upload is multipart, handled
by the router with `Form`/`File`, not a JSON body schema).

`BrandAssetOut` never exposes `storage_path` (mirrors `app.visual_audit.schemas.
VisualAssetOut`): `signed_url` is computed at the service/router boundary.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.brand_assets.models import BrandAssetType


class BrandAssetOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    brand_dna_version_id: uuid.UUID | None
    type: BrandAssetType
    signed_url: str
    metadata: dict[str, Any]
    created_at: datetime


class BrandAssetList(BaseModel):
    assets: list[BrandAssetOut]
