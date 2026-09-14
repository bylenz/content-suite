"""Offline PostgreSQL-shape tests for the knowledge repository and embedding type.

CI runs SQLite only (design.md seam); these compile the PostgreSQL branches
against the `postgresql` dialect to assert the production SQL/binding shape
without a live database. Live pgvector verification stays task 10.2 (pending).
"""

import uuid
from typing import cast

from sqlalchemy import Table, TextClause
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateTable
from sqlalchemy.types import TypeDecorator

from app.knowledge import repository
from app.knowledge.models import (
    BrandKnowledgeChunk,
    Embedding,
    KnowledgeScope,
    _PgVector,
)

PG = postgresql.dialect()


def _rank_statement(scopes: list[KnowledgeScope]) -> TextClause:
    return repository._rank_semantic_sql(
        brand_id=uuid.uuid4(),
        brand_dna_version_id=uuid.uuid4(),
        scopes=scopes,
        query_vector=[1.0, 0.0],
        top_k=8,
    )


def test_pg_ranking_scope_in_uses_expanding_binding_not_a_plain_tuple() -> None:
    compiled = str(_rank_statement([KnowledgeScope.TEXT, KnowledgeScope.BOTH]).compile(dialect=PG))

    # Expanding bindparam engaged: one value per scope at execution time.
    # The broken plain-tuple form would render a single `IN (%(scopes)s)` param.
    # `scope::text` (not bare `scope`): psycopg3 declares this expanding string
    # bindparam with an explicit ::VARCHAR type, which blocks Postgres's usual
    # unknown-literal-to-enum coercion and raises `operator does not exist:
    # knowledge_scope = character varying` against a real `knowledge_scope`
    # column (verified against live Supabase/pgvector) — invisible to this
    # compile-only check until the assertion itself names the cast.
    assert "scope::text IN (__[POSTCOMPILE_scopes])" in compiled
    assert "IN (%(scopes)s)" not in compiled


def test_pg_ranking_carries_plain_scope_enum_values() -> None:
    statement = _rank_statement([KnowledgeScope.TEXT, KnowledgeScope.BOTH])
    params = statement.compile(dialect=PG).construct_params()

    assert params["scopes"] == ["TEXT", "BOTH"]
    assert params["query"] == "[1.0,0.0]"


def test_pg_ranking_filters_before_sort_with_deterministic_total_order() -> None:
    compiled = str(_rank_statement([KnowledgeScope.TEXT, KnowledgeScope.BOTH]).compile(dialect=PG))

    assert "embedding <=> CAST(%(query)s AS vector)" in compiled
    where_clause = compiled.index("WHERE")
    for filter_fragment in (
        "brand_id = %(brand_id)s::UUID",
        "brand_dna_version_id = %(version_id)s::UUID",
        "AND scope::text IN",
    ):
        assert where_clause < compiled.index(filter_fragment) < compiled.index("ORDER BY")
    assert "ORDER BY distance ASC, id ASC" in compiled
    assert compiled.rstrip().endswith("LIMIT %(top_k)s")


def test_pg_embedding_column_is_native_vector_not_varchar() -> None:
    table = cast(Table, BrandKnowledgeChunk.__table__)
    pg_ddl = str(CreateTable(table).compile(dialect=PG))
    sqlite_ddl = str(CreateTable(table).compile(dialect=sqlite.dialect()))

    assert "embedding VECTOR NOT NULL" in pg_ddl
    assert "embedding JSON NOT NULL" in sqlite_ddl


def test_pg_embedding_write_is_pgvector_literal_text_not_varchar_bind() -> None:
    impl = cast(TypeDecorator, Embedding().dialect_impl(PG))

    assert isinstance(impl.impl_instance, _PgVector)
    bind = impl.bind_processor(PG)
    assert bind is not None
    assert bind([0.1, 0.25, -1.0]) == "[0.1,0.25,-1.0]"
    result = impl.result_processor(PG, None)
    assert result is not None
    assert result("[0.1,0.25,-1.0]") == [0.1, 0.25, -1.0]


def test_sqlite_embedding_uses_the_json_impl() -> None:
    impl = cast(TypeDecorator, Embedding().dialect_impl(sqlite.dialect()))

    assert not isinstance(impl.impl_instance, _PgVector)
    # JSON impl serializes the raw list (no pgvector literal text on SQLite).
    bind = impl.bind_processor(sqlite.dialect())
    assert bind is not None
    assert bind([0.1, 0.25]) == "[0.1, 0.25]"
