"""add jobs.llm_followup_fields

The tagger can now route an ambiguity into a QUESTION instead of resolving
it by guessing a hazard tag: asked "how do I change my light bulb", it puts
`height_access` in `ask` rather than inferring `work_at_height` from a
ceiling it was never told about.

Those requested fields are persisted for the same reason `llm_hazard_ids`
is: the set of questions the user is ASKED must be the set assessment scores
against. Deriving them fresh at each step would let assessment escalate on a
field the intake flow never showed — the exact bug e5f7c1a92b40 fixed for
hazard ids.

NULL = never tagged (LLM unavailable at creation); [] = tagged, nothing extra
to ask. Existing rows get NULL and are re-tagged lazily on next use.

Revision ID: b9d5a3e17c62
Revises: f3b8d2c47a15
"""

import sqlalchemy as sa

from alembic import op

revision = "b9d5a3e17c62"
down_revision = "f3b8d2c47a15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("llm_followup_fields", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "llm_followup_fields")
