"""Offline PostgreSQL-shape tests for the TRUNCATE-revoke migration.

Mirrors the offline pattern of tests/test_rls_migration_sql.py: exercises the
migration's PostgreSQL branch with a recording `op` proxy (no network, no
live database). Live Supabase verification (has_table_privilege evidence)
stays in openspec/changes/007-supabase-rls-hardening/tasks.md 3.3.
"""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

MIGRATION_FILE = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "e3dfa0780566_revoke_truncate_anon_authenticated.py"
)

DOMAIN_TABLES = (
    "profiles",
    "brands",
    "brand_memberships",
    "brand_dna_versions",
    "brand_knowledge_chunks",
)

EXPECTED_PG_UPGRADE = [
    f"REVOKE TRUNCATE ON TABLE {table} FROM anon, authenticated" for table in DOMAIN_TABLES
]

EXPECTED_PG_DOWNGRADE = [
    f"GRANT TRUNCATE ON TABLE {table} TO anon, authenticated" for table in DOMAIN_TABLES
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
    spec = importlib.util.spec_from_file_location(
        f"truncate_revoke_migration_under_test_{dialect_name}", MIGRATION_FILE
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    recorder = _RecordingOp(dialect_name)
    migration: Any = module
    migration.op = recorder
    return module, recorder


def test_pg_upgrade_revokes_truncate_on_exactly_the_five_domain_tables() -> None:
    module, recorder = _load_migration("postgresql")
    module.upgrade()  # type: ignore[attr-defined]
    assert recorder.executed == EXPECTED_PG_UPGRADE


def test_pg_upgrade_only_touches_truncate_for_anon_and_authenticated() -> None:
    module, recorder = _load_migration("postgresql")
    module.upgrade()  # type: ignore[attr-defined]
    for statement in recorder.executed:
        assert statement.startswith("REVOKE TRUNCATE ON TABLE")
        assert "anon" in statement
        assert "authenticated" in statement
        for other_privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            assert other_privilege not in statement


def test_pg_downgrade_regrants_truncate_in_order() -> None:
    module, recorder = _load_migration("postgresql")
    module.upgrade()  # type: ignore[attr-defined]
    recorder.executed.clear()
    module.downgrade()  # type: ignore[attr-defined]
    assert recorder.executed == EXPECTED_PG_DOWNGRADE


def test_sqlite_branch_is_an_explicit_noop() -> None:
    module, recorder = _load_migration("sqlite")
    module.upgrade()  # type: ignore[attr-defined]
    assert recorder.executed == []
    recorder.executed.clear()
    module.downgrade()  # type: ignore[attr-defined]
    assert recorder.executed == []
