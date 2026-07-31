"""make job.urgency nullable

The conversational intake no longer asks "how urgent is this?" and nothing
consumes the value: it is excluded from the classifier as a non-safety
feature (see ml/train_baseline.py) and the rule engine ignores it entirely.
Asking for it cost the user a step in a safety flow and bought nothing.

The column is made nullable rather than dropped, so existing rows keep their
value and the change is reversible. srs.md FR-02 records the decision.

Revision ID: d3ab19f4c7e1
Revises: c2dc0749bae6
"""

import sqlalchemy as sa

from alembic import op

revision = "d3ab19f4c7e1"
down_revision = "c2dc0749bae6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "jobs",
        "urgency",
        existing_type=sa.String(length=50),
        nullable=True,
    )


def downgrade() -> None:
    # Rows written after the upgrade may have NULL urgency, which the
    # original NOT NULL constraint would reject. Backfill before restoring
    # it so the downgrade cannot fail on real data.
    op.execute("UPDATE jobs SET urgency = 'not_specified' WHERE urgency IS NULL")
    op.alter_column(
        "jobs",
        "urgency",
        existing_type=sa.String(length=50),
        nullable=False,
    )
