"""add jobs.llm_hazard_ids

The LLM hazard tagger used to run only at assessment time, while the
follow-up gate (which decides what the user is asked) ran off keyword
matches alone. The two sets could disagree: "replace my ceiling fans" hits
no keyword, so no follow-up was asked, but the tagger flagged
`fixed_wiring_work` at assessment, which made `power_isolated` required —
and unanswered — escalating the task to level 5 over a question the user
was never shown.

Persisting the tagged ids at creation makes both steps read the same hazard
set, so the gate and the escalation cannot drift apart.

NULL = not tagged yet (LLM was unavailable at creation); [] = tagged, no
hazards. Existing rows get NULL and are re-tagged lazily on next use.

Revision ID: e5f7c1a92b40
Revises: d3ab19f4c7e1
"""

import sqlalchemy as sa

from alembic import op

revision = "e5f7c1a92b40"
down_revision = "d3ab19f4c7e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("llm_hazard_ids", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "llm_hazard_ids")
