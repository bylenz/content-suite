"""merge brand_dna_versions_brief and visual_compliance_tables heads

Revision ID: 01db85ad4b09
Revises: 275cd7fbad9a, fb2104e57358
Create Date: 2026-09-14 02:46:32.275063

No-op merge: `fb2104e57358` (013-brand-dna-generation's `brief` column on
`brand_dna_versions`) and `275cd7fbad9a` (008-visual-compliance's storage +
visual audit tables) both branched off `836153016bcf` independently while
developed in parallel. Both changes are already fully applied; this
revision only joins the two branches so the chain has a single head again.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "01db85ad4b09"
down_revision: str | tuple[str, ...] | None = ("275cd7fbad9a", "fb2104e57358")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
