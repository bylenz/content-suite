"""supabase RLS hardening: enable RLS + member-scoped read-only policies

Revision ID: 597b7798962f
Revises: c4a9b2e6f8d1
Create Date: 2026-09-21 10:00:00.000000

Dialect branches (design.md):
- PostgreSQL (canonical, Supabase): `ENABLE ROW LEVEL SECURITY` on the five
  domain tables in `public` plus five read policies `FOR SELECT TO
  authenticated`. `anon` gets no policy (default deny), and no
  INSERT/UPDATE/DELETE policy exists for anyone: writes stay exclusive to the
  application's owner connection (RLS does not apply to the table owner
  without FORCE, which this migration never sets). Domain invariants
  (versioning, workflow, Creator-only mutations) are FastAPI's authority.
- SQLite (dev/test seam): explicit no-op; SQLite has no RLS.

Idempotency: `ENABLE ROW LEVEL SECURITY` is idempotent and every
`CREATE POLICY` is preceded by its `DROP POLICY IF EXISTS`.

Identity contract: policies rely on `auth.uid() = profiles.id` (the verified
JWT `sub` is the `profiles` PK; asserted by tests/test_rls_migration_sql.py).

`service_role` (Supabase secret key) has BYPASSRLS: it is a server-side
secret that must never reach the client. This migration does not touch the
`auth` schema.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "597b7798962f"
down_revision: str | None = "c4a9b2e6f8d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DOMAIN_TABLES = (
    "profiles",
    "brands",
    "brand_memberships",
    "brand_dna_versions",
    "brand_knowledge_chunks",
)

# (policy name, table, predicate): all FOR SELECT TO authenticated only.
READ_POLICIES = (
    ("rls_profiles_select_self", "profiles", "id = auth.uid()"),
    ("rls_brand_memberships_select_own", "brand_memberships", "profile_id = auth.uid()"),
    (
        "rls_brands_select_members",
        "brands",
        "EXISTS (SELECT 1 FROM brand_memberships m "
        "WHERE m.profile_id = auth.uid() AND m.brand_id = brands.id)",
    ),
    (
        "rls_brand_dna_versions_select_members",
        "brand_dna_versions",
        "EXISTS (SELECT 1 FROM brand_memberships m "
        "WHERE m.profile_id = auth.uid() AND m.brand_id = brand_dna_versions.brand_id)",
    ),
    (
        "rls_brand_knowledge_chunks_select_members",
        "brand_knowledge_chunks",
        "EXISTS (SELECT 1 FROM brand_memberships m "
        "WHERE m.profile_id = auth.uid() AND m.brand_id = brand_knowledge_chunks.brand_id)",
    ),
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return  # SQLite dev/test seam: no RLS exists there; explicit no-op.

    for table in DOMAIN_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    for name, table, predicate in READ_POLICIES:
        op.execute(f"DROP POLICY IF EXISTS {name} ON {table}")
        op.execute(
            f"CREATE POLICY {name} ON {table} "
            f"FOR SELECT TO authenticated USING ({predicate})"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    for name, table, _predicate in READ_POLICIES:
        op.execute(f"DROP POLICY IF EXISTS {name} ON {table}")
    for table in DOMAIN_TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
