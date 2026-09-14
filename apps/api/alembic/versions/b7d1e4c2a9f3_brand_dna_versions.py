"""brand_dna_versions table with enums, unique version and partial draft/active indexes

Revision ID: b7d1e4c2a9f3
Revises: dec022b4c864
Create Date: 2026-09-13 15:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7d1e4c2a9f3"
down_revision: str | None = "dec022b4c864"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "brand_dna_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("brand_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "ACTIVE", "ARCHIVED", name="brand_dna_status"),
            nullable=False,
        ),
        # Portable JSON; canonical target is PostgreSQL (jsonb-compatible storage).
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "knowledge_status",
            sa.Enum(
                "NOT_SYNCED",
                "SYNCING",
                "SYNCED",
                "OUTDATED",
                "FAILED",
                name="brand_dna_knowledge_status",
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"], name=op.f("fk_brand_dna_versions_brand_id_brands")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["profiles.id"], name=op.f("fk_brand_dna_versions_created_by_profiles")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_brand_dna_versions")),
        sa.UniqueConstraint("brand_id", "version", name=op.f("uq_brand_dna_versions_brand_id")),
    )
    # One DRAFT and one ACTIVE per brand, enforced at the database level.
    op.create_index(
        "uq_brand_dna_versions_draft_per_brand",
        "brand_dna_versions",
        ["brand_id"],
        unique=True,
        postgresql_where=sa.text("status = 'DRAFT'"),
        sqlite_where=sa.text("status = 'DRAFT'"),
    )
    op.create_index(
        "uq_brand_dna_versions_active_per_brand",
        "brand_dna_versions",
        ["brand_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
        sqlite_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index("uq_brand_dna_versions_active_per_brand", table_name="brand_dna_versions")
    op.drop_index("uq_brand_dna_versions_draft_per_brand", table_name="brand_dna_versions")
    op.drop_table("brand_dna_versions")
    sa.Enum(name="brand_dna_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="brand_dna_knowledge_status").drop(op.get_bind(), checkfirst=True)
