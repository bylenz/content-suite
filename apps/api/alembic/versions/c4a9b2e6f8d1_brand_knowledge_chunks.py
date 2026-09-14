"""brand_knowledge_chunks + sync evidence columns on brand_dna_versions

Revision ID: c4a9b2e6f8d1
Revises: b7d1e4c2a9f3
Create Date: 2026-09-20 10:00:00.000000

Embedding column is dialect-dependent (design.md):
- PostgreSQL (canonical, Supabase): `CREATE EXTENSION IF NOT EXISTS vector` and a
  `vector` column WITHOUT a fixed dimension (exact `<=>` scan does not need one
  and the dimension stays decoupled from the embedding model).
- SQLite (dev/test seam only): a JSON column with the list of floats; the
  repository ranks in Python. This branch is an honest test seam, NOT a
  simulation of production vector search — CI never claims pgvector parity.

The `vector` extension is intentionally NOT dropped on downgrade: it is a shared
cluster-level facility that other objects may already depend on.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4a9b2e6f8d1"
down_revision: str | None = "b7d1e4c2a9f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "brand_dna_versions", sa.Column("knowledge_embedding_model", sa.String(), nullable=True)
    )
    op.add_column(
        "brand_dna_versions",
        sa.Column("knowledge_embedding_dimensions", sa.Integer(), nullable=True),
    )
    op.add_column(
        "brand_dna_versions", sa.Column("knowledge_fingerprint", sa.String(), nullable=True)
    )
    op.create_table(
        "brand_knowledge_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("brand_id", sa.Uuid(), nullable=False),
        sa.Column("brand_dna_version_id", sa.Uuid(), nullable=False),
        sa.Column("section", sa.Text(), nullable=False),
        sa.Column("rule_type", sa.Text(), nullable=False),
        sa.Column(
            "scope", sa.Enum("TEXT", "VISUAL", "BOTH", name="knowledge_scope"), nullable=False
        ),
        sa.Column("mandatory", sa.Boolean(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"], name=op.f("fk_brand_knowledge_chunks_brand_id_brands")
        ),
        sa.ForeignKeyConstraint(
            ["brand_dna_version_id"],
            ["brand_dna_versions.id"],
            name=op.f("fk_brand_knowledge_chunks_brand_dna_version_id_brand_dna_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_brand_knowledge_chunks")),
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        # Vector column without a fixed typmod: dimension stays decoupled from the model.
        op.execute("ALTER TABLE brand_knowledge_chunks ADD COLUMN embedding vector NOT NULL")
    else:
        # SQLite seam: JSON list of floats (see module docstring).
        op.add_column(
            "brand_knowledge_chunks", sa.Column("embedding", sa.JSON(), nullable=False)
        )
    op.create_index(
        "ix_brand_knowledge_chunks_brand_version",
        "brand_knowledge_chunks",
        ["brand_id", "brand_dna_version_id"],
    )
    op.create_index(
        "ix_brand_knowledge_chunks_mandatory_per_version",
        "brand_knowledge_chunks",
        ["brand_dna_version_id"],
        postgresql_where=sa.text("mandatory IS TRUE"),
        sqlite_where=sa.text("mandatory = 1"),
    )
    op.create_index(
        "ix_brand_knowledge_chunks_scope_per_version",
        "brand_knowledge_chunks",
        ["brand_dna_version_id", "scope"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_brand_knowledge_chunks_scope_per_version", table_name="brand_knowledge_chunks"
    )
    op.drop_index(
        "ix_brand_knowledge_chunks_mandatory_per_version", table_name="brand_knowledge_chunks"
    )
    op.drop_index(
        "ix_brand_knowledge_chunks_brand_version", table_name="brand_knowledge_chunks"
    )
    op.drop_table("brand_knowledge_chunks")
    sa.Enum(name="knowledge_scope").drop(op.get_bind(), checkfirst=True)
    op.drop_column("brand_dna_versions", "knowledge_fingerprint")
    op.drop_column("brand_dna_versions", "knowledge_embedding_dimensions")
    op.drop_column("brand_dna_versions", "knowledge_embedding_model")
