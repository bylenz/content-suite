"""observability_trace_index read model (change 009)

Revision ID: a3d8f2c6e9b1
Revises: e1f4a7c9d3b2
Create Date: 2026-09-20 12:00:00.000000

Additive table: one sanitized, allowlisted row per recorded span (scalar
metadata only — never raw prompts, responses, tokens or secrets). `trace_id`
is nullable because the no-op tracer produces none; `brand_id` is nullable
but such rows are unreachable through the facade (no authorization path).
Indexes match tasks.md 1.1 exactly: (brand_id, created_at DESC) for the
brand-scoped listing and (entity_type, entity_id) for entity lookups.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3d8f2c6e9b1"
down_revision: str | None = "e1f4a7c9d3b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "observability_trace_index",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.String(), nullable=True),
        sa.Column("brand_id", sa.Uuid(), nullable=True),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("operation", sa.String(), nullable=True),
        sa.Column("prompt_version", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("outcome", sa.Enum("ok", "error", name="trace_outcome"), nullable=False),
        sa.Column("error_type", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"], name=op.f("fk_observability_trace_index_brand_id_brands")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_observability_trace_index")),
    )
    op.create_index(
        "ix_observability_trace_index_brand_created",
        "observability_trace_index",
        ["brand_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_observability_trace_index_entity",
        "observability_trace_index",
        ["entity_type", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_observability_trace_index_entity", table_name="observability_trace_index")
    op.drop_index(
        "ix_observability_trace_index_brand_created", table_name="observability_trace_index"
    )
    op.drop_table("observability_trace_index")
    sa.Enum(name="trace_outcome").drop(op.get_bind(), checkfirst=True)
