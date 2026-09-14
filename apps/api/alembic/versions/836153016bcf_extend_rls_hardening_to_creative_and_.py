"""extend RLS hardening: creative_items, creative_versions, workflow_events,
content_reviews, observability_trace_index

Revision ID: 836153016bcf
Revises: a31264bda9ea
Create Date: 2026-09-14 00:51:26.541868

Closes the gap `e1f4a7c9d3b2` and `a31264bda9ea` documented and deferred to
"007 when finalized": those migrations created five tables that follow the
module-table pattern but never enabled RLS, so — per the default grants
`e3dfa0780566` documents (`anon`/`authenticated` get full table-level
SELECT/INSERT/UPDATE/DELETE on every new `public` table) — any authenticated
Supabase user could read or write any other tenant's creative items, drafts,
workflow history and review decisions directly through the Supabase Data API
(PostgREST), bypassing every brand-membership check FastAPI's service layer
enforces. This migration finalizes that pending work.

Dialect branches (mirrors `597b7798962f`):
- PostgreSQL (canonical, Supabase): `ENABLE ROW LEVEL SECURITY` on the five
  tables plus five read policies `FOR SELECT TO authenticated`. `anon` gets no
  policy (default deny), and no INSERT/UPDATE/DELETE policy exists for
  anyone: writes stay exclusive to the application's owner connection, same
  as the original five domain tables. TRUNCATE is also revoked from
  `anon`/`authenticated` on all five (mirrors `e3dfa0780566`'s defense in
  depth: RLS does not govern TRUNCATE).
- SQLite (dev/test seam): explicit no-op; SQLite has no RLS.

Membership evidence: `creative_items` and `observability_trace_index` carry
`brand_id` directly, so their predicate matches `brand_dna_versions`'s
single-source form. `creative_versions`, `workflow_events` and
`content_reviews` only carry `creative_item_id`, so their predicate joins
through `creative_items` to reach `brand_memberships` — two sources instead
of one, but still acyclic (neither policy's USING queries the table it
protects).

Idempotency: `ENABLE ROW LEVEL SECURITY` is idempotent, every `CREATE POLICY`
is preceded by its `DROP POLICY IF EXISTS`, and `REVOKE` on an already-absent
privilege is a no-op.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "836153016bcf"
down_revision: str | None = "a31264bda9ea"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DOMAIN_TABLES = (
    "creative_items",
    "creative_versions",
    "workflow_events",
    "content_reviews",
    "observability_trace_index",
)

GRANTEES = ("anon", "authenticated")

_ITEM_MEMBERSHIP_JOIN = (
    "EXISTS (SELECT 1 FROM creative_items ci "
    "JOIN brand_memberships m ON m.brand_id = ci.brand_id "
    "WHERE ci.id = {table}.creative_item_id AND m.profile_id = auth.uid())"
)

# (policy name, table, predicate): all FOR SELECT TO authenticated only.
READ_POLICIES = (
    (
        "rls_creative_items_select_members",
        "creative_items",
        "EXISTS (SELECT 1 FROM brand_memberships m "
        "WHERE m.profile_id = auth.uid() AND m.brand_id = creative_items.brand_id)",
    ),
    (
        "rls_creative_versions_select_members",
        "creative_versions",
        _ITEM_MEMBERSHIP_JOIN.format(table="creative_versions"),
    ),
    (
        "rls_workflow_events_select_members",
        "workflow_events",
        _ITEM_MEMBERSHIP_JOIN.format(table="workflow_events"),
    ),
    (
        "rls_content_reviews_select_members",
        "content_reviews",
        _ITEM_MEMBERSHIP_JOIN.format(table="content_reviews"),
    ),
    (
        "rls_observability_trace_index_select_members",
        "observability_trace_index",
        "EXISTS (SELECT 1 FROM brand_memberships m "
        "WHERE m.profile_id = auth.uid() AND m.brand_id = observability_trace_index.brand_id)",
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
    for table in DOMAIN_TABLES:
        op.execute(f"REVOKE TRUNCATE ON TABLE {table} FROM {', '.join(GRANTEES)}")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    for table in DOMAIN_TABLES:
        op.execute(f"GRANT TRUNCATE ON TABLE {table} TO {', '.join(GRANTEES)}")
    for name, table, _predicate in READ_POLICIES:
        op.execute(f"DROP POLICY IF EXISTS {name} ON {table}")
    for table in DOMAIN_TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
