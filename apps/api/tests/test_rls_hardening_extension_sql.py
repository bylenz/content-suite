"""Offline PostgreSQL-shape tests for the RLS hardening extension migration
(836153016bcf), mirroring tests/test_rls_migration_sql.py's pattern for the
five tables 007 deferred: creative_items, creative_versions, workflow_events,
content_reviews, observability_trace_index.
"""

import importlib.util
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

MIGRATION_FILE = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "836153016bcf_extend_rls_hardening_to_creative_and_.py"
)

DOMAIN_TABLES = (
    "creative_items",
    "creative_versions",
    "workflow_events",
    "content_reviews",
    "observability_trace_index",
)

# Expected PostgreSQL statements, in order.
EXPECTED_PG_UPGRADE = [
    "ALTER TABLE creative_items ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE creative_versions ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE workflow_events ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE content_reviews ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE observability_trace_index ENABLE ROW LEVEL SECURITY",
    "DROP POLICY IF EXISTS rls_creative_items_select_members ON creative_items",
    "CREATE POLICY rls_creative_items_select_members ON creative_items "
    "FOR SELECT TO authenticated USING (EXISTS (SELECT 1 FROM brand_memberships m "
    "WHERE m.profile_id = auth.uid() AND m.brand_id = creative_items.brand_id))",
    "DROP POLICY IF EXISTS rls_creative_versions_select_members ON creative_versions",
    "CREATE POLICY rls_creative_versions_select_members ON creative_versions "
    "FOR SELECT TO authenticated USING (EXISTS (SELECT 1 FROM creative_items ci "
    "JOIN brand_memberships m ON m.brand_id = ci.brand_id "
    "WHERE ci.id = creative_versions.creative_item_id AND m.profile_id = auth.uid()))",
    "DROP POLICY IF EXISTS rls_workflow_events_select_members ON workflow_events",
    "CREATE POLICY rls_workflow_events_select_members ON workflow_events "
    "FOR SELECT TO authenticated USING (EXISTS (SELECT 1 FROM creative_items ci "
    "JOIN brand_memberships m ON m.brand_id = ci.brand_id "
    "WHERE ci.id = workflow_events.creative_item_id AND m.profile_id = auth.uid()))",
    "DROP POLICY IF EXISTS rls_content_reviews_select_members ON content_reviews",
    "CREATE POLICY rls_content_reviews_select_members ON content_reviews "
    "FOR SELECT TO authenticated USING (EXISTS (SELECT 1 FROM creative_items ci "
    "JOIN brand_memberships m ON m.brand_id = ci.brand_id "
    "WHERE ci.id = content_reviews.creative_item_id AND m.profile_id = auth.uid()))",
    "DROP POLICY IF EXISTS rls_observability_trace_index_select_members "
    "ON observability_trace_index",
    "CREATE POLICY rls_observability_trace_index_select_members ON observability_trace_index "
    "FOR SELECT TO authenticated USING (EXISTS (SELECT 1 FROM brand_memberships m "
    "WHERE m.profile_id = auth.uid() AND m.brand_id = observability_trace_index.brand_id))",
    "REVOKE TRUNCATE ON TABLE creative_items FROM anon, authenticated",
    "REVOKE TRUNCATE ON TABLE creative_versions FROM anon, authenticated",
    "REVOKE TRUNCATE ON TABLE workflow_events FROM anon, authenticated",
    "REVOKE TRUNCATE ON TABLE content_reviews FROM anon, authenticated",
    "REVOKE TRUNCATE ON TABLE observability_trace_index FROM anon, authenticated",
]

EXPECTED_PG_DOWNGRADE = [
    "GRANT TRUNCATE ON TABLE creative_items TO anon, authenticated",
    "GRANT TRUNCATE ON TABLE creative_versions TO anon, authenticated",
    "GRANT TRUNCATE ON TABLE workflow_events TO anon, authenticated",
    "GRANT TRUNCATE ON TABLE content_reviews TO anon, authenticated",
    "GRANT TRUNCATE ON TABLE observability_trace_index TO anon, authenticated",
    "DROP POLICY IF EXISTS rls_creative_items_select_members ON creative_items",
    "DROP POLICY IF EXISTS rls_creative_versions_select_members ON creative_versions",
    "DROP POLICY IF EXISTS rls_workflow_events_select_members ON workflow_events",
    "DROP POLICY IF EXISTS rls_content_reviews_select_members ON content_reviews",
    "DROP POLICY IF EXISTS rls_observability_trace_index_select_members "
    "ON observability_trace_index",
    "ALTER TABLE creative_items DISABLE ROW LEVEL SECURITY",
    "ALTER TABLE creative_versions DISABLE ROW LEVEL SECURITY",
    "ALTER TABLE workflow_events DISABLE ROW LEVEL SECURITY",
    "ALTER TABLE content_reviews DISABLE ROW LEVEL SECURITY",
    "ALTER TABLE observability_trace_index DISABLE ROW LEVEL SECURITY",
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
        f"rls_extension_migration_under_test_{dialect_name}", MIGRATION_FILE
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


def test_pg_upgrade_enables_rls_on_exactly_the_five_deferred_tables() -> None:
    executed = _upgrade_statements("postgresql")
    enables = sorted(s for s in executed if "ENABLE ROW LEVEL SECURITY" in s)
    expected = sorted(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" for table in DOMAIN_TABLES)
    assert enables == expected


def test_pg_upgrade_executes_the_exact_statement_set_in_order() -> None:
    assert _upgrade_statements("postgresql") == EXPECTED_PG_UPGRADE


def test_pg_policies_are_read_only_and_scoped_to_authenticated() -> None:
    executed = _upgrade_statements("postgresql")
    creates = [s for s in executed if s.startswith("CREATE POLICY")]
    assert len(creates) == 5
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


def test_pg_revokes_truncate_from_anon_and_authenticated_on_all_five() -> None:
    executed = _upgrade_statements("postgresql")
    revokes = sorted(s for s in executed if s.startswith("REVOKE TRUNCATE"))
    expected = sorted(
        f"REVOKE TRUNCATE ON TABLE {table} FROM anon, authenticated" for table in DOMAIN_TABLES
    )
    assert revokes == expected


def test_pg_create_policy_is_always_preceded_by_its_drop_policy_if_exists() -> None:
    executed = _upgrade_statements("postgresql")
    for index, statement in enumerate(executed):
        if statement.startswith("CREATE POLICY"):
            name = statement.split()[2]
            table = statement.split(" ON ")[1].split(" ")[0]
            assert executed[index - 1] == f"DROP POLICY IF EXISTS {name} ON {table}"


def test_pg_policy_using_never_queries_the_table_it_protects() -> None:
    # Same anti-recursion invariant as test_rls_migration_sql.py, adapted: the
    # three item-scoped tables draw membership evidence from creative_items
    # AND brand_memberships (a two-hop join), not brand_memberships alone.
    executed = _upgrade_statements("postgresql")
    for statement in executed:
        if not statement.startswith("CREATE POLICY"):
            continue
        table = statement.split(" ON ")[1].split(" ")[0]
        predicate = statement.split("USING (", 1)[1]
        sources = set(re.findall(r"\bFROM\s+([a-z_]+)", predicate)) | set(
            re.findall(r"\bJOIN\s+([a-z_]+)", predicate)
        )
        assert table not in sources  # no self-reference inside its own USING
        if table in ("creative_items", "observability_trace_index"):
            assert sources == {"brand_memberships"}
        else:
            assert sources == {"creative_items", "brand_memberships"}


def test_pg_downgrade_reverses_upgrade_in_order() -> None:
    module, recorder = _load_migration("postgresql")
    module.upgrade()  # type: ignore[attr-defined]
    recorder.executed.clear()
    module.downgrade()  # type: ignore[attr-defined]
    assert recorder.executed == EXPECTED_PG_DOWNGRADE


def test_pg_statements_never_target_the_auth_schema() -> None:
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
