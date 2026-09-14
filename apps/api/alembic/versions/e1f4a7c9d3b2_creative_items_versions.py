"""creative_items, creative_versions and workflow_events with enums

Revision ID: e1f4a7c9d3b2
Revises: 597b7798962f
Create Date: 2026-09-21 12:00:00.000000

RLS note (change 007 owns hardening): this migration follows the module-table
pattern (brand_dna_versions, brand_knowledge_chunks) and does not enable RLS
itself; `836153016bcf` enables RLS and adds member-scoped read policies for
`creative_items`, `creative_versions` and `workflow_events`.

Portability: `brief`/`output`/`applied_rule_ids`/`consistency_result` use JSON
(SQLite tests + PostgreSQL jsonb semantics); `applied_rule_ids` stores the
validated rule-ref strings (ai.contracts RuleRef) instead of a native uuid[].
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f4a7c9d3b2"
down_revision: str | None = "597b7798962f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "creative_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("brand_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "PRODUCT_DESCRIPTION", "VIDEO_SCRIPT", "IMAGE_PROMPT", name="creative_item_type"
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column(
            "workflow_status",
            sa.Enum(
                "DRAFT",
                "PENDING_CONTENT_REVIEW",
                "CONTENT_CHANGES_REQUESTED",
                "CONTENT_APPROVED",
                "PENDING_VISUAL_REVIEW",
                "VISUAL_CHANGES_REQUESTED",
                "FINAL_APPROVED",
                name="creative_workflow_status",
            ),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"], name=op.f("fk_creative_items_brand_id_brands")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["profiles.id"], name=op.f("fk_creative_items_created_by_profiles")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_creative_items")),
    )
    op.create_index(
        op.f("ix_creative_items_brand_id"), "creative_items", ["brand_id"], unique=False
    )

    op.create_table(
        "creative_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creative_item_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("brand_dna_version_id", sa.Uuid(), nullable=True),
        sa.Column(
            "origin",
            sa.Enum("AI_GENERATED", "AI_REGENERATED", "HUMAN_EDIT", name="creative_version_origin"),
            nullable=False,
        ),
        # Portable JSON; canonical target is PostgreSQL (jsonb-compatible storage).
        sa.Column("brief", sa.JSON(), nullable=False),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("applied_rule_ids", sa.JSON(), nullable=False),
        sa.Column("consistency_result", sa.JSON(), nullable=True),
        sa.Column("consistency_score", sa.Numeric(), nullable=True),
        sa.Column("langfuse_trace_id", sa.String(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["brand_dna_version_id"],
            ["brand_dna_versions.id"],
            name=op.f("fk_creative_versions_brand_dna_version_id_brand_dna_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["creative_item_id"],
            ["creative_items.id"],
            name=op.f("fk_creative_versions_creative_item_id_creative_items"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["profiles.id"], name=op.f("fk_creative_versions_created_by_profiles")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_creative_versions")),
        sa.UniqueConstraint(
            "creative_item_id", "version", name="uq_creative_versions_item_version"
        ),
    )
    op.create_index(
        "ix_creative_versions_creative_item_id", "creative_versions", ["creative_item_id"]
    )

    op.create_table(
        "workflow_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creative_item_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["profiles.id"], name=op.f("fk_workflow_events_actor_id_profiles")
        ),
        sa.ForeignKeyConstraint(
            ["creative_item_id"],
            ["creative_items.id"],
            name=op.f("fk_workflow_events_creative_item_id_creative_items"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_events")),
    )
    op.create_index(
        "ix_workflow_events_creative_item_id", "workflow_events", ["creative_item_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_events_creative_item_id", table_name="workflow_events")
    op.drop_table("workflow_events")
    op.drop_index("ix_creative_versions_creative_item_id", table_name="creative_versions")
    op.drop_table("creative_versions")
    op.drop_index(op.f("ix_creative_items_brand_id"), table_name="creative_items")
    op.drop_table("creative_items")
    sa.Enum(name="creative_version_origin").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="creative_workflow_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="creative_item_type").drop(op.get_bind(), checkfirst=True)
