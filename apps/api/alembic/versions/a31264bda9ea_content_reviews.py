"""content_reviews (change 009-content-governance)

Revision ID: a31264bda9ea
Revises: a73adfcae836
Create Date: 2026-09-14 09:05:00.000000

`creative_items.workflow_status` and `workflow_events` already exist
(e1f4a7c9d3b2, Creative Studio) with the full `creative_workflow_status`
enum including the visual states change 008 will use later, so this
migration only adds the one table content-governance needs: `content_reviews`.

RLS note (change 007 owns hardening, same gap already open for
`creative_items`/`creative_versions`/`workflow_events`): this table follows
the module-table pattern and does not enable RLS itself; `836153016bcf`
enables RLS and adds a member-scoped read policy for all four.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a31264bda9ea"
down_revision: str | None = "a73adfcae836"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creative_item_id", sa.Uuid(), nullable=False),
        sa.Column("submitted_version_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), nullable=False),
        sa.Column(
            "decision",
            sa.Enum("APPROVED", "CHANGES_REQUESTED", name="content_review_decision"),
            nullable=False,
        ),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["creative_item_id"],
            ["creative_items.id"],
            name=op.f("fk_content_reviews_creative_item_id_creative_items"),
        ),
        sa.ForeignKeyConstraint(
            ["submitted_version_id"],
            ["creative_versions.id"],
            name=op.f("fk_content_reviews_submitted_version_id_creative_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"], ["profiles.id"], name=op.f("fk_content_reviews_reviewer_id_profiles")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_reviews")),
        # Safety net (design.md): domain logic never depends on this constraint,
        # it only guards against an uncaught race producing a duplicate decision.
        sa.UniqueConstraint(
            "creative_item_id",
            "submitted_version_id",
            "decision",
            name="uq_content_reviews_item_version_decision",
        ),
    )
    op.create_index(
        "ix_content_reviews_creative_item_id", "content_reviews", ["creative_item_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_content_reviews_creative_item_id", table_name="content_reviews")
    op.drop_table("content_reviews")
    sa.Enum(name="content_review_decision").drop(op.get_bind(), checkfirst=True)
