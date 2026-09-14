"""revoke TRUNCATE from anon/authenticated on the five RLS domain tables

Revision ID: e3dfa0780566
Revises: 597b7798962f
Create Date: 2026-09-14 05:00:00.000000

Context (007-supabase-rls-hardening, task 3.3 production verification):
Supabase grants `anon`/`authenticated` full table-level privileges
(`SELECT/INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER`) by default on
every table created in `public` (`ALTER DEFAULT PRIVILEGES` set up by the
project's `postgres` owner at project creation) — this is Supabase platform
bootstrap, not something 597b7798962f added. Row Level Security governs
row-level SELECT/INSERT/UPDATE/DELETE, but it does NOT govern `TRUNCATE`
(a table-level operation invisible to policies), so the default grant left
`TRUNCATE` reachable by `anon`/`authenticated` on the five domain tables
despite RLS being enabled.

Practical exposure is narrow (PostgREST/Supabase Data API never issues
`TRUNCATE`, and `anon`/`authenticated` are NOLOGIN roles unreachable without
an already-privileged direct Postgres connection), but this migration closes
it anyway as an explicit defense-in-depth layer, verified in production
(evidence in tasks.md 3.3): `has_table_privilege('anon'|'authenticated',
'<table>', 'TRUNCATE')` must be `false` on all five domain tables.

Dialect branches (mirrors 597b7798962f):
- PostgreSQL (canonical, Supabase): `REVOKE TRUNCATE` on the five domain
  tables from `anon` and `authenticated`. No other privilege is touched:
  SELECT/INSERT/UPDATE/DELETE stay grantable (RLS is the operative gate);
  only the table-level operation RLS cannot reach is removed.
- SQLite (dev/test seam): explicit no-op; `anon`/`authenticated` roles and
  `TRUNCATE` grants do not exist there.

Idempotency: `REVOKE` is idempotent (revoking an already-absent privilege is
a no-op, not an error).

Branches off 597b7798962f directly (not the repo's current true head) since
this closes a gap found in 007's own production verification and is
independent of the unrelated, still-in-progress changes stacked on top of
it; a later merge migration reconciles multiple heads when those land.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3dfa0780566"
down_revision: str | None = "597b7798962f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DOMAIN_TABLES = (
    "profiles",
    "brands",
    "brand_memberships",
    "brand_dna_versions",
    "brand_knowledge_chunks",
)

GRANTEES = ("anon", "authenticated")


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return  # SQLite dev/test seam: no roles/grants exist there.

    for table in DOMAIN_TABLES:
        op.execute(f"REVOKE TRUNCATE ON TABLE {table} FROM {', '.join(GRANTEES)}")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    for table in DOMAIN_TABLES:
        op.execute(f"GRANT TRUNCATE ON TABLE {table} TO {', '.join(GRANTEES)}")
