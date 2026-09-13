"""initial identity tables: profiles, brands, brand_memberships (DATA_MODEL.md)

Revision ID: dec022b4c864
Revises:
Create Date: 2026-09-13 13:57:03.092158

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dec022b4c864"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "brands",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_brands")),
        sa.UniqueConstraint("slug", name=op.f("uq_brands_slug")),
    )
    op.create_table(
        "profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_profiles")),
        sa.UniqueConstraint("email", name=op.f("uq_profiles_email")),
    )
    op.create_table(
        "brand_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("brand_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("CREATOR", "CONTENT_REVIEWER", "VISUAL_REVIEWER", name="brand_role"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"], name=op.f("fk_brand_memberships_brand_id_brands")
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["profiles.id"], name=op.f("fk_brand_memberships_profile_id_profiles")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_brand_memberships")),
        sa.UniqueConstraint("profile_id", "brand_id", name=op.f("uq_brand_memberships_profile_id")),
    )


def downgrade() -> None:
    op.drop_table("brand_memberships")
    sa.Enum(name="brand_role").drop(op.get_bind(), checkfirst=True)
    op.drop_table("profiles")
    op.drop_table("brands")
