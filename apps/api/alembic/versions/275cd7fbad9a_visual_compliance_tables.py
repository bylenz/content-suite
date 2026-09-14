"""visual_compliance_tables (change 008-visual-compliance)

Revision ID: 275cd7fbad9a
Revises: 836153016bcf
Create Date: 2026-09-14 02:00:10.928489

Creates the three tables the Visual Compliance domain owns
(DATA_MODEL.md + design.md D8): `visual_assets` (immutable visual versions
linked to a `CONTENT_APPROVED` creative item), `visual_audits` (Vision
findings/score/applied-context snapshots, insert-only per re-run) and
`visual_reviews` (insert-only reviewer decisions with HIGH-exception
evidence). `creative_items.workflow_status` already carries the visual
states (`e1f4a7c9d3b2`); this migration adds no new enum values there.

RLS from day one (D8, unlike `e1f4a7c9d3b2`/`a31264bda9ea` which deferred it
to 007): this change lands after 007, so it follows the finalized pattern
directly instead of opening a new gap. PostgreSQL: `ENABLE ROW LEVEL
SECURITY` + one `FOR SELECT TO authenticated` member-scoped policy per table,
no write policies for anyone (writes stay exclusive to the application's
owner connection). Membership evidence chains through the existing tables:
`visual_assets` -> `creative_items` -> `brand_memberships` (two-hop, same
shape as `creative_versions`); `visual_audits` -> `visual_assets` ->
`creative_items` -> `brand_memberships` (three-hop); `visual_reviews` ->
`visual_audits` -> `visual_assets` -> `creative_items` -> `brand_memberships`
(four-hop). None of the three USING predicates reference the table they
protect. SQLite dev/test seam: explicit no-op, same as 007/007-extension.

Portability: `metadata`/`checks`/`findings`/`applied_context`/`evidence` use
JSON (SQLite tests + PostgreSQL jsonb semantics), mirroring
`creative_versions`/`workflow_events`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "275cd7fbad9a"
down_revision: str | None = "836153016bcf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GRANTEES = ("anon", "authenticated")

# (policy name, table, predicate): all FOR SELECT TO authenticated only.
READ_POLICIES = (
    (
        "rls_visual_assets_select_members",
        "visual_assets",
        "EXISTS (SELECT 1 FROM creative_items ci "
        "JOIN brand_memberships m ON m.brand_id = ci.brand_id "
        "WHERE ci.id = visual_assets.creative_item_id AND m.profile_id = auth.uid())",
    ),
    (
        "rls_visual_audits_select_members",
        "visual_audits",
        "EXISTS (SELECT 1 FROM visual_assets va "
        "JOIN creative_items ci ON ci.id = va.creative_item_id "
        "JOIN brand_memberships m ON m.brand_id = ci.brand_id "
        "WHERE va.id = visual_audits.visual_asset_id AND m.profile_id = auth.uid())",
    ),
    (
        "rls_visual_reviews_select_members",
        "visual_reviews",
        "EXISTS (SELECT 1 FROM visual_audits vad "
        "JOIN visual_assets va ON va.id = vad.visual_asset_id "
        "JOIN creative_items ci ON ci.id = va.creative_item_id "
        "JOIN brand_memberships m ON m.brand_id = ci.brand_id "
        "WHERE vad.id = visual_reviews.visual_audit_id AND m.profile_id = auth.uid())",
    ),
)

DOMAIN_TABLES = ("visual_assets", "visual_audits", "visual_reviews")


def _apply_rls() -> None:
    """PostgreSQL-only RLS enablement + read policies; SQLite is an explicit no-op.

    Factored out so `tests/test_visual_compliance_migration_sql.py` can drive
    it offline (a stubbed `op.execute`/`op.get_bind`) without invoking the
    real `op.create_table` calls in `upgrade()` (mirrors the 007-pattern
    tests, which only ever had RLS statements to record).
    """
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in DOMAIN_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    for name, table, predicate in READ_POLICIES:
        op.execute(f"DROP POLICY IF EXISTS {name} ON {table}")
        op.execute(
            f"CREATE POLICY {name} ON {table} "
            f"FOR SELECT TO authenticated USING ({predicate})"
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
        "visual_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creative_item_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["creative_item_id"],
            ["creative_items.id"],
            name=op.f("fk_visual_assets_creative_item_id_creative_items"),
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"], ["profiles.id"], name=op.f("fk_visual_assets_uploaded_by_profiles")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visual_assets")),
        sa.UniqueConstraint(
            "creative_item_id", "version", name="uq_visual_assets_item_version"
        ),
    )
    op.create_index("ix_visual_assets_creative_item_id", "visual_assets", ["creative_item_id"])

    op.create_table(
        "visual_audits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("visual_asset_id", sa.Uuid(), nullable=False),
        sa.Column("brand_dna_version_id", sa.Uuid(), nullable=False),
        sa.Column("checks", sa.JSON(), nullable=False),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("score", sa.Numeric(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        # Snapshot of the applied context (rule count/scope), never the raw
        # prompt or provider response (design D6: sanitized evidence only).
        sa.Column("applied_context", sa.JSON(), nullable=False),
        sa.Column("langfuse_trace_id", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["visual_asset_id"],
            ["visual_assets.id"],
            name=op.f("fk_visual_audits_visual_asset_id_visual_assets"),
        ),
        sa.ForeignKeyConstraint(
            ["brand_dna_version_id"],
            ["brand_dna_versions.id"],
            name=op.f("fk_visual_audits_brand_dna_version_id_brand_dna_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visual_audits")),
    )
    op.create_index("ix_visual_audits_visual_asset_id", "visual_audits", ["visual_asset_id"])

    op.create_table(
        "visual_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("visual_audit_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), nullable=False),
        sa.Column(
            "decision",
            sa.Enum("APPROVED", "CHANGES_REQUESTED", name="visual_review_decision"),
            nullable=False,
        ),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column(
            "exception_accepted", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        # HIGH-fail finding evidence persisted with the decision (design D7);
        # null when the approval had no HIGH findings to except.
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["visual_audit_id"],
            ["visual_audits.id"],
            name=op.f("fk_visual_reviews_visual_audit_id_visual_audits"),
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"], ["profiles.id"], name=op.f("fk_visual_reviews_reviewer_id_profiles")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visual_reviews")),
        # Safety net (design D7): domain logic checks-before-insert for
        # idempotency; this constraint only guards against an uncaught race.
        sa.UniqueConstraint(
            "visual_audit_id",
            "reviewer_id",
            "decision",
            name="uq_visual_reviews_audit_reviewer_decision",
        ),
    )
    op.create_index("ix_visual_reviews_visual_audit_id", "visual_reviews", ["visual_audit_id"])

    _apply_rls()


def downgrade() -> None:
    _revert_rls()

    op.drop_index("ix_visual_reviews_visual_audit_id", table_name="visual_reviews")
    op.drop_table("visual_reviews")
    sa.Enum(name="visual_review_decision").drop(op.get_bind(), checkfirst=True)
    op.drop_index("ix_visual_audits_visual_asset_id", table_name="visual_audits")
    op.drop_table("visual_audits")
    op.drop_index("ix_visual_assets_creative_item_id", table_name="visual_assets")
    op.drop_table("visual_assets")
