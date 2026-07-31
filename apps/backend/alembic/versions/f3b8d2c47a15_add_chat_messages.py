"""add chat_messages

The chat thread lived only in React state, so refreshing the page lost the
conversation; re-opening a job from the sidebar rebuilt an approximation of
it rather than replaying what was said. This table stores the transcript,
owned by the user and scoped to a job.

Note what the table does NOT have: any column for a risk level, hazard list
or explanation. A risk_card row is a positional marker only, re-rendered
from risk_assessments at read time, so the transcript can never show a
verdict that has drifted from the assessment of record.

Revision ID: f3b8d2c47a15
Revises: e5f7c1a92b40
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "f3b8d2c47a15"
down_revision = "e5f7c1a92b40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="text"),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_chat_messages_user_id", "chat_messages", ["user_id"])
    op.create_index("ix_chat_messages_job_id", "chat_messages", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_messages_job_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_user_id", table_name="chat_messages")
    op.drop_table("chat_messages")
