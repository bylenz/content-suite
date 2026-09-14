"""brand_assets (change 012-brand-assets)

Revision ID: e512ca7e7f5b
Revises: 01db85ad4b09
Create Date: 2026-09-14 03:00:00.000000

Creates `brand_assets` (DATA_MODEL.md): the brand's PRIMARY_LOGO/ALT_LOGO
single-slot logos plus the unbounded VISUAL_REFERENCE collection, backed by
`private-storage` (008) for the object itself. `brand_dna_version_id` is a
nullable audit snapshot (the ACTIVE Brand DNA version at upload time), not an
ownership relation -- the asset stays valid regardless of later publications.

Partial unique index `uq_brand_assets_slot_per_brand` enforces the single-slot
invariant at the DB level (`(brand_id, type)` unique only for `PRIMARY_LOGO`/
`ALT_LOGO`), mirroring `brand_dna_versions`'s DRAFT/ACTIVE partial-unique
pattern; `VISUAL_REFERENCE` rows are excluded so the collection stays
unbounded. `ix_brand_assets_brand_id` supports the brand-scoped list query.

RLS from day one (design.md, same discipline `275cd7fbad9a` already
established for 008 -- explicitly not repeating the gap `e1f4a7c9d3b2`/
`a31264bda9ea` opened and `836153016bcf` had to close later): PostgreSQL gets
`ENABLE ROW LEVEL SECURITY` + one `FOR SELECT TO authenticated` member-scoped
read policy, no write policy for anyone (writes stay exclusive to the
application's owner connection), and TRUNCATE revoked from `anon`/
`authenticated`. `brand_assets` carries `brand_id` directly, so its predicate
is single-source, same shape as `brand_dna_versions`. SQLite dev/test seam:
explicit no-op, same as every prior RLS migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e512ca7e7f5b"
down_revision: str | None = "01db85ad4b09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GRANTEES = ("anon", "authenticated")

DOMAIN_TABLES = ("brand_assets",)

# (policy name, table, predicate): all FOR SELECT TO authenticated only.
READ_POLICIES = (
    (
        "rls_brand_assets_select_members",
        "brand_assets",
        "EXISTS (SELECT 1 FROM brand_memberships m "
        "WHERE m.profile_id = auth.uid() AND m.brand_id = brand_assets.brand_id)",
    ),
)


def _apply_rls() -> None:
    """PostgreSQL-only RLS enablement + read policy; SQLite is an explicit
    no-op. Factored out so an offline SQL test can drive it with a stubbed
    `op` (mirrors `tests/test_visual_compliance_migration_sql.py`)."""
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in DOMAIN_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    for name, table, predicate in READ_POLICIES:
        op.execute(f"DROP POLICY IF EXISTS {name} ON {table}")
        op.execute(
            f"CREATE POLICY {name} ON {table} FOR SELECT TO authenticated USING ({predicate})"
        )
    for table in DOMAIN_TABLES:
        op.execute(f"REVOKE TRUNCATE ON TABLE {table} FROM {', '.join(GRANTEES)}")


def _revert_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in DOMAIN_TABLES:
        op.execute(f"GRANT TRUNCATE ON TABLE {table} TO {', '.join(GRANTEES)}")
    for name, table, _predicate in READ_POLICIES:
        op.execute(f"DROP POLICY IF EXISTS {name} ON {table}")
    for table in DOMAIN_TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    op.create_table(
        "brand_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("brand_id", sa.Uuid(), nullable=False),
        sa.Column("brand_dna_version_id", sa.Uuid(), nullable=True),
        sa.Column(
            "type",
            sa.Enum("PRIMARY_LOGO", "ALT_LOGO", "VISUAL_REFERENCE", name="brand_asset_type"),
            nullable=False,
        ),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"], name=op.f("fk_brand_assets_brand_id_brands")
        ),
        sa.ForeignKeyConstraint(
            ["brand_dna_version_id"],
            ["brand_dna_versions.id"],
            name=op.f("fk_brand_assets_brand_dna_version_id_brand_dna_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_brand_assets")),
    )
    op.create_index("ix_brand_assets_brand_id", "brand_assets", ["brand_id"])
    op.create_index(
        "uq_brand_assets_slot_per_brand",
        "brand_assets",
        ["brand_id", "type"],
        unique=True,
        sqlite_where=sa.text("type IN ('PRIMARY_LOGO', 'ALT_LOGO')"),
        postgresql_where=sa.text("type IN ('PRIMARY_LOGO', 'ALT_LOGO')"),
    )

    _apply_rls()


def downgrade() -> None:
    _revert_rls()

    op.drop_index("uq_brand_assets_slot_per_brand", table_name="brand_assets")
    op.drop_index("ix_brand_assets_brand_id", table_name="brand_assets")
    op.drop_table("brand_assets")
    sa.Enum(name="brand_asset_type").drop(op.get_bind(), checkfirst=True)
