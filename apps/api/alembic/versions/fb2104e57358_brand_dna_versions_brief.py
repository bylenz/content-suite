"""brief column on brand_dna_versions

Revision ID: fb2104e57358
Revises: 836153016bcf
Create Date: 2026-09-14 09:00:00.000000

Change 013 (brand-dna-generation): the brief that originated an AI generation
is conserved alongside the resulting DRAFT, distinct from `document`. Same
pattern as `creative_versions.brief` (portable JSON; canonical target is
PostgreSQL jsonb-compatible storage). Nullable: a version born from manual
authoring, or any version predating this change, has no brief.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fb2104e57358"
down_revision: str | None = "836153016bcf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("brand_dna_versions", sa.Column("brief", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("brand_dna_versions", "brief")
