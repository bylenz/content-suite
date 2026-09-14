"""Offline PostgreSQL-shape tests for the brand_assets migration
(e512ca7e7f5b), mirroring tests/test_visual_compliance_migration_sql.py's
pattern: only `_apply_rls`/`_revert_rls` (the RLS-emitting helpers) are driven
here with a stubbed `op`, no real table DDL and no live database. The real
`op.create_table`/`op.create_index` round trip is covered separately by
`uv run alembic upgrade head && downgrade -1 && upgrade head` on SQLite.
"""

import importlib.util
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

MIGRATION_FILE = (
    Path(__file__).resolve().parents[1] / "alembic" / "versions" / "e512ca7e7f5b_brand_assets.py"
)

DOMAIN_TABLES = ("brand_assets",)

EXPECTED_PG_UPGRADE = [
    "ALTER TABLE brand_assets ENABLE ROW LEVEL SECURITY",
    "DROP POLICY IF EXISTS rls_brand_assets_select_members ON brand_assets",
    "CREATE POLICY rls_brand_assets_select_members ON brand_assets "
    "FOR SELECT TO authenticated USING (EXISTS (SELECT 1 FROM brand_memberships m "
    "WHERE m.profile_id = auth.uid() AND m.brand_id = brand_assets.brand_id))",
    "REVOKE TRUNCATE ON TABLE brand_assets FROM anon, authenticated",
]

EXPECTED_PG_DOWNGRADE = [
    "GRANT TRUNCATE ON TABLE brand_assets TO anon, authenticated",
    "DROP POLICY IF EXISTS rls_brand_assets_select_members ON brand_assets",
    "ALTER TABLE brand_assets DISABLE ROW LEVEL SECURITY",
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
        f"brand_assets_migration_under_test_{dialect_name}", MIGRATION_FILE
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    recorder = _RecordingOp(dialect_name)
    migration: Any = module
    migration.op = recorder
    return module, recorder


def _upgrade_rls_statements(dialect_name: str) -> list[str]:
    module, recorder = _load_migration(dialect_name)
    module._apply_rls()  # type: ignore[attr-defined]
    return recorder.executed


def test_pg_enables_rls_on_brand_assets() -> None:
    executed = _upgrade_rls_statements("postgresql")
    enables = sorted(s for s in executed if "ENABLE ROW LEVEL SECURITY" in s)
    expected = sorted(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" for table in DOMAIN_TABLES)
    assert enables == expected


def test_pg_apply_rls_executes_the_exact_statement_set_in_order() -> None:
    assert _upgrade_rls_statements("postgresql") == EXPECTED_PG_UPGRADE


def test_pg_policy_is_read_only_and_scoped_to_authenticated() -> None:
    executed = _upgrade_rls_statements("postgresql")
    creates = [s for s in executed if s.startswith("CREATE POLICY")]
    assert len(creates) == 1
    for statement in creates:
        assert " FOR SELECT TO authenticated " in statement
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


def test_pg_revokes_truncate_from_anon_and_authenticated() -> None:
    executed = _upgrade_rls_statements("postgresql")
    revokes = sorted(s for s in executed if s.startswith("REVOKE TRUNCATE"))
    expected = sorted(
        f"REVOKE TRUNCATE ON TABLE {table} FROM anon, authenticated" for table in DOMAIN_TABLES
    )
    assert revokes == expected


def test_pg_create_policy_is_always_preceded_by_its_drop_policy_if_exists() -> None:
    executed = _upgrade_rls_statements("postgresql")
    for index, statement in enumerate(executed):
        if statement.startswith("CREATE POLICY"):
            name = statement.split()[2]
            table = statement.split(" ON ")[1].split(" ")[0]
            assert executed[index - 1] == f"DROP POLICY IF EXISTS {name} ON {table}"


def test_pg_policy_using_never_queries_the_table_it_protects() -> None:
    executed = _upgrade_rls_statements("postgresql")
    for statement in executed:
        if not statement.startswith("CREATE POLICY"):
            continue
        table = statement.split(" ON ")[1].split(" ")[0]
        predicate = statement.split("USING (", 1)[1]
        sources = set(re.findall(r"\bFROM\s+([a-z_]+)", predicate)) | set(
            re.findall(r"\bJOIN\s+([a-z_]+)", predicate)
        )
        assert table not in sources  # no self-reference inside its own USING
    assets_predicate = next(
        s for s in executed if s.startswith("CREATE POLICY rls_brand_assets")
    ).split("USING (", 1)[1]
    assert set(re.findall(r"\b(?:FROM|JOIN)\s+([a-z_]+)", assets_predicate)) == {
        "brand_memberships"
    }


def test_pg_downgrade_reverses_upgrade_in_order() -> None:
    module, recorder = _load_migration("postgresql")
    module._apply_rls()  # type: ignore[attr-defined]
    recorder.executed.clear()
    module._revert_rls()  # type: ignore[attr-defined]
    assert recorder.executed == EXPECTED_PG_DOWNGRADE


def test_pg_statements_never_target_the_auth_schema() -> None:
    executed = _upgrade_rls_statements("postgresql")
    assert any("auth.uid()" in statement for statement in executed)
    for statement in executed:
        assert " ON auth." not in statement
        assert not statement.startswith("ALTER TABLE auth.")


def test_sqlite_branch_is_an_explicit_noop() -> None:
    module, recorder = _load_migration("sqlite")
    module._apply_rls()  # type: ignore[attr-defined]
    assert recorder.executed == []
    recorder.executed.clear()
    module._revert_rls()  # type: ignore[attr-defined]
    assert recorder.executed == []


def test_slot_partial_unique_index_declared_in_source() -> None:
    """Static check on the migration source (no DB): the single-slot
    invariant (design.md D1) is enforced by a partial unique index restricted
    to PRIMARY_LOGO/ALT_LOGO, and the brand-scoped lookup index exists."""
    source = MIGRATION_FILE.read_text()
    assert 'name="uq_brand_assets_slot_per_brand"' not in source  # it's an index, not a named UC
    assert '"uq_brand_assets_slot_per_brand"' in source
    assert "type IN ('PRIMARY_LOGO', 'ALT_LOGO')" in source
    assert '"ix_brand_assets_brand_id"' in source
