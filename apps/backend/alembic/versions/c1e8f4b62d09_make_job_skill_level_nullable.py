"""make jobs.skill_level nullable

`user_skill` was retired from the product on 2026-08-02, the same way
`urgency` was on 2026-07-31 and for the same reason: nothing consumes it, so
asking cost the user a step in a safety flow and bought nothing.

Two things had to be true before this was safe, and both were measured
rather than assumed:

  * It stopped being a classifier feature. The seed data originally chose
    `user_skill` to fit each example's narrative, which put 91% of
    `Experienced` rows on level 4 and left levels 1-3 with none, so the model
    learned the dropdown instead of the task. After ml/rebalance_skill.py the
    two are independent (NMI 0.657 -> 0.000) and skill became the weakest
    coefficient block in the model — the prediction is now identical across
    all three values.
  * Only one rule used it. `electrical_work_by_beginner` (floor 3) is
    deleted; `fixed_wiring_work` carries floor 3 for everyone now, so
    beginners land exactly where they did and srs.md §9's intent survives
    without depending on an unverifiable self-report (srs.md §3).

The column is kept rather than dropped so existing rows survive and the
change is reversible. Downgrade re-imposes NOT NULL, backfilling any rows
written since with 'Beginner' — the value the classifier used as its
fallback — because the old schema cannot represent NULL.

Revision ID: c1e8f4b62d09
Revises: b9d5a3e17c62
"""

import sqlalchemy as sa

from alembic import op

revision = "c1e8f4b62d09"
down_revision = "b9d5a3e17c62"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("jobs", "skill_level", existing_type=sa.String(50), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE jobs SET skill_level = 'Beginner' WHERE skill_level IS NULL")
    op.alter_column("jobs", "skill_level", existing_type=sa.String(50), nullable=False)
