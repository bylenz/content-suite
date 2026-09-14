"""merge observability_trace_index and RLS TRUNCATE-revoke heads

Revision ID: a73adfcae836
Revises: a3d8f2c6e9b1, e3dfa0780566
Create Date: 2026-09-14 09:00:00.000000

No-op merge: `e3dfa0780566` (007-supabase-rls-hardening's TRUNCATE-revoke
follow-up) branched directly off `597b7798962f` instead of the repo's true
head at the time, anticipating exactly this reconciliation (see that
migration's own docstring). `a3d8f2c6e9b1` (observability_trace_index,
change 009-observability-facade) is the other head. Both changes are already
fully applied; this revision only joins the two branches so the chain has a
single head again before 009-content-governance adds `content_reviews`.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "a73adfcae836"
down_revision: str | tuple[str, ...] | None = ("a3d8f2c6e9b1", "e3dfa0780566")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
