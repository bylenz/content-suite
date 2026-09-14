"""Offline PostgreSQL-shape tests for the Supabase RLS hardening migration.

CI runs SQLite only; these exercise the migration's PostgreSQL branch with a
recording `op` proxy (no network, no live database), mirroring the offline
pattern of tests/test_knowledge_postgres_sql.py. Live Supabase verification
(ledger reconciliation, owner/role check, catalog + grants evidence) stays
task 3.3 (pending, out of scope here).

Also asserts the identity contract the policies rely on: the verified JWT
`sub` is the `profiles` PK used as `AuthenticatedUser.id`, and roles or
memberships never come from the client.
"""

import dataclasses
import importlib.util
import re
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import Settings
from app.identity.auth import AuthenticatedUser, get_current_user
from app.identity.models import Brand, BrandMembership, BrandRole, Profile
from app.identity.repository import get_membership, get_profile
from tests.conftest import TEST_JWT_AUDIENCE, TEST_JWT_ISSUER, TEST_JWT_SECRET, make_token

MIGRATION_FILE = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "597b7798962f_supabase_rls_hardening.py"
)

# Expected PostgreSQL statements, in order (design.md "Políticas exactas").
EXPECTED_PG_UPGRADE = [
    "ALTER TABLE profiles ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE brands ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE brand_memberships ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE brand_dna_versions ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE brand_knowledge_chunks ENABLE ROW LEVEL SECURITY",
    "DROP POLICY IF EXISTS rls_profiles_select_self ON profiles",
    "CREATE POLICY rls_profiles_select_self ON profiles "
    "FOR SELECT TO authenticated USING (id = auth.uid())",
    "DROP POLICY IF EXISTS rls_brand_memberships_select_own ON brand_memberships",
    "CREATE POLICY rls_brand_memberships_select_own ON brand_memberships "
    "FOR SELECT TO authenticated USING (profile_id = auth.uid())",
    "DROP POLICY IF EXISTS rls_brands_select_members ON brands",
    "CREATE POLICY rls_brands_select_members ON brands "
    "FOR SELECT TO authenticated USING (EXISTS (SELECT 1 FROM brand_memberships m "
    "WHERE m.profile_id = auth.uid() AND m.brand_id = brands.id))",
    "DROP POLICY IF EXISTS rls_brand_dna_versions_select_members ON brand_dna_versions",
    "CREATE POLICY rls_brand_dna_versions_select_members ON brand_dna_versions "
    "FOR SELECT TO authenticated USING (EXISTS (SELECT 1 FROM brand_memberships m "
    "WHERE m.profile_id = auth.uid() AND m.brand_id = brand_dna_versions.brand_id))",
    "DROP POLICY IF EXISTS rls_brand_knowledge_chunks_select_members ON brand_knowledge_chunks",
    "CREATE POLICY rls_brand_knowledge_chunks_select_members ON brand_knowledge_chunks "
    "FOR SELECT TO authenticated USING (EXISTS (SELECT 1 FROM brand_memberships m "
    "WHERE m.profile_id = auth.uid() AND m.brand_id = brand_knowledge_chunks.brand_id))",
]

EXPECTED_PG_DOWNGRADE = [
    "DROP POLICY IF EXISTS rls_profiles_select_self ON profiles",
    "DROP POLICY IF EXISTS rls_brand_memberships_select_own ON brand_memberships",
    "DROP POLICY IF EXISTS rls_brands_select_members ON brands",
    "DROP POLICY IF EXISTS rls_brand_dna_versions_select_members ON brand_dna_versions",
    "DROP POLICY IF EXISTS rls_brand_knowledge_chunks_select_members ON brand_knowledge_chunks",
    "ALTER TABLE profiles DISABLE ROW LEVEL SECURITY",
    "ALTER TABLE brands DISABLE ROW LEVEL SECURITY",
    "ALTER TABLE brand_memberships DISABLE ROW LEVEL SECURITY",
    "ALTER TABLE brand_dna_versions DISABLE ROW LEVEL SECURITY",
    "ALTER TABLE brand_knowledge_chunks DISABLE ROW LEVEL SECURITY",
]


class _RecordingOp:
    """Minimal `alembic.op` stand-in: records `op.execute` for one dialect."""

    def __init__(self, dialect_name: str) -> None:
        self.executed: list[str] = []
        self._bind = SimpleNamespace(dialect=SimpleNamespace(name=dialect_name))

    def get_bind(self) -> SimpleNamespace:
        return self._bind

    def execute(self, sql: Any) -> None:
        self.executed.append(str(sql))


def _load_migration(dialect_name: str) -> tuple[Any, _RecordingOp]:
    """Import the migration file and patch its `op` with a recorder (no DB)."""
    spec = importlib.util.spec_from_file_location(
        f"rls_migration_under_test_{dialect_name}", MIGRATION_FILE
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    recorder = _RecordingOp(dialect_name)
    migration: Any = module
    migration.op = recorder
    return module, recorder


def _upgrade_statements(dialect_name: str) -> list[str]:
    module, recorder = _load_migration(dialect_name)
    module.upgrade()  # type: ignore[attr-defined]
    return recorder.executed


def test_pg_upgrade_enables_rls_on_exactly_the_five_domain_tables() -> None:
    executed = _upgrade_statements("postgresql")
    enables = sorted(s for s in executed if "ENABLE ROW LEVEL SECURITY" in s)
    expected = sorted(
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"
        for table in (
            "profiles",
            "brands",
            "brand_memberships",
            "brand_dna_versions",
            "brand_knowledge_chunks",
        )
    )
    assert enables == expected  # exactly five tables, no other table touched


def test_pg_upgrade_executes_the_exact_policy_set_in_order() -> None:
    # Full-sequence equality: covers predicates, order, and DROP-before-CREATE idempotency.
    assert _upgrade_statements("postgresql") == EXPECTED_PG_UPGRADE


def test_pg_policies_are_read_only_and_scoped_to_authenticated() -> None:
    executed = _upgrade_statements("postgresql")
    creates = [s for s in executed if s.startswith("CREATE POLICY")]
    assert len(creates) == 5
    for statement in creates:
        assert " FOR SELECT TO authenticated " in statement
    # No write policy of any kind, no PUBLIC/anon scope, no FORCE anywhere.
    joined = "\n".join(executed)
    for forbidden in (
        "FOR INSERT",
        "FOR UPDATE",
        "FOR DELETE",
        "FOR ALL",
        "TO PUBLIC",
        "TO anon",
        "FORCE ROW LEVEL SECURITY",
    ):
        assert forbidden not in joined


def test_pg_create_policy_is_always_preceded_by_its_drop_policy_if_exists() -> None:
    executed = _upgrade_statements("postgresql")
    for index, statement in enumerate(executed):
        if statement.startswith("CREATE POLICY"):
            name = statement.split()[2]
            table = statement.split(" ON ")[1].split(" ")[0]
            assert executed[index - 1] == f"DROP POLICY IF EXISTS {name} ON {table}"


def test_pg_policy_using_never_queries_the_table_it_protects() -> None:
    # Dedicated anti-recursion invariant (design.md): no policy's USING may
    # reference the table it protects as a query source (self-reference would
    # recurse), and brand-table policies draw membership evidence only from
    # brand_memberships — the policy reference graph stays acyclic.
    executed = _upgrade_statements("postgresql")
    for statement in executed:
        if not statement.startswith("CREATE POLICY"):
            continue
        table = statement.split(" ON ")[1].split(" ")[0]
        predicate = statement.split("USING (", 1)[1]
        sources = set(re.findall(r"\bFROM\s+([a-z_]+)", predicate))
        assert table not in sources  # no self-reference inside its own USING
        if table in ("profiles", "brand_memberships"):
            # Own-row policies compare columns directly: no subquery sources.
            assert sources == set()
        else:
            # Brand tables: membership evidence comes only from brand_memberships.
            assert sources == {"brand_memberships"}


def test_pg_downgrade_drops_policies_and_disables_rls_in_order() -> None:
    module, recorder = _load_migration("postgresql")
    module.upgrade()  # type: ignore[attr-defined]
    recorder.executed.clear()
    module.downgrade()  # type: ignore[attr-defined]
    assert recorder.executed == EXPECTED_PG_DOWNGRADE


def test_pg_statements_never_target_the_auth_schema() -> None:
    # auth.uid() must appear (identity contract) but no DDL may target auth.* objects.
    executed = _upgrade_statements("postgresql")
    assert any("auth.uid()" in statement for statement in executed)
    for statement in executed:
        assert " ON auth." not in statement
        assert not statement.startswith("ALTER TABLE auth.")


def test_sqlite_branch_is_an_explicit_noop() -> None:
    module, recorder = _load_migration("sqlite")
    module.upgrade()  # type: ignore[attr-defined]
    assert recorder.executed == []
    recorder.executed.clear()
    module.downgrade()  # type: ignore[attr-defined]
    assert recorder.executed == []


def _auth_settings() -> Settings:
    return Settings(
        auth_jwt_secret=TEST_JWT_SECRET,
        auth_jwt_issuer=TEST_JWT_ISSUER,
        auth_jwt_audience=TEST_JWT_AUDIENCE,
    )


def test_identity_contract_verified_sub_is_authenticated_user_id() -> None:
    profile_id = uuid.uuid4()
    # Client-supplied role/membership claims are present but must never surface.
    token = make_token(
        sub=str(profile_id),
        email="member@example.com",
        role="CREATOR",
        user_metadata={"brand_memberships": [{"brand_id": str(uuid.uuid4()), "role": "CREATOR"}]},
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    user = get_current_user(credentials, _auth_settings())

    assert user.id == profile_id  # auth.uid() == profiles.id contract
    assert user.email == "member@example.com"
    # Only verified identity leaves the auth boundary: no roles, no memberships.
    assert {field.name for field in dataclasses.fields(AuthenticatedUser)} == {"id", "email"}


def test_identity_contract_services_resolve_memberships_by_profiles_pk(session: Session) -> None:
    profile = Profile(id=uuid.uuid4(), email="rls-contract@example.com")
    brand = Brand(id=uuid.uuid4(), name="RLS Contract", slug="rls-contract")
    session.add_all(
        [
            profile,
            brand,
            BrandMembership(
                id=uuid.uuid4(), profile_id=profile.id, brand_id=brand.id, role=BrandRole.CREATOR
            ),
        ]
    )
    session.commit()

    # The same id the RLS policies compare with auth.uid() resolves the profile PK
    # and the membership rows server-side.
    fetched_profile = get_profile(session, profile.id)
    assert fetched_profile is not None
    assert fetched_profile.id == profile.id
    membership = get_membership(session, profile.id, brand.id)
    assert membership is not None
    assert membership.profile_id == profile.id
    assert membership.role == BrandRole.CREATOR
