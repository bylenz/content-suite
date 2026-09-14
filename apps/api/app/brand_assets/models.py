"""ORM model for brand assets (DATA_MODEL.md): primary/alt logo slots plus a
visual-reference collection, backed by `private-storage` (008).

Insert/delete-only (design.md 012): there is no UPDATE path for
`storage_path`. "Replacing" a `PRIMARY_LOGO`/`ALT_LOGO` is delete-old-row +
insert-new-row in one transaction (see `app.brand_assets.service`), never an
in-place update -- same discipline `creative_versions`/`workflow_events`
already follow. No `updated_at` column exists, consistent with that.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BrandAssetType(enum.StrEnum):
    PRIMARY_LOGO = "PRIMARY_LOGO"
    ALT_LOGO = "ALT_LOGO"
    VISUAL_REFERENCE = "VISUAL_REFERENCE"


# Types that occupy a single slot per brand (uploading one replaces the
# existing row of that type); VISUAL_REFERENCE is a collection instead.
SINGLE_SLOT_TYPES = frozenset({BrandAssetType.PRIMARY_LOGO, BrandAssetType.ALT_LOGO})


class BrandAsset(Base):
    __tablename__ = "brand_assets"
    __table_args__ = (
        Index("ix_brand_assets_brand_id", "brand_id"),
        # Partial unique index (mirrors brand_dna_versions' DRAFT/ACTIVE
        # pattern): at most one PRIMARY_LOGO and one ALT_LOGO per brand,
        # enforced at the DB level as a safety net under the row lock this
        # module's service already takes. VISUAL_REFERENCE rows are excluded
        # (unbounded collection, no slot semantics).
        Index(
            "uq_brand_assets_slot_per_brand",
            "brand_id",
            "type",
            unique=True,
            sqlite_where=text("type IN ('PRIMARY_LOGO', 'ALT_LOGO')"),
            postgresql_where=text("type IN ('PRIMARY_LOGO', 'ALT_LOGO')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id"))
    # Audit snapshot (design.md), not an ownership relation: the ACTIVE Brand
    # DNA version id at upload time, nullable when the brand has none yet.
    # The asset stays valid/readable regardless of later publications.
    brand_dna_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("brand_dna_versions.id")
    )
    type: Mapped[BrandAssetType] = mapped_column(Enum(BrandAssetType, name="brand_asset_type"))
    storage_path: Mapped[str] = mapped_column(Text())
    asset_metadata: Mapped[dict] = mapped_column("metadata", JSON())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
