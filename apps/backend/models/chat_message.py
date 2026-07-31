"""ChatMessage model — the conversation transcript for a job.

Why this exists: the chat thread used to live only in React state, so a page
refresh lost it. Re-opening a job from the sidebar rebuilt an *approximation*
of the conversation (the task description plus a fresh risk card), not what
was actually said. This table stores the real transcript, owned by the user.

WHAT IS DELIBERATELY NOT STORED HERE
------------------------------------
The risk verdict. A `kind="risk_card"` row carries no risk level, no hazard
list and no explanation — only a marker saying "the card belongs at this point
in the conversation". The card is re-rendered from the `risk_assessments` row
at read time.

That is a safety property, not a storage optimisation: a second copy of a
verdict in the chat log could drift from the assessment of record (if an
assessment is ever re-run, corrected, or invalidated) and the user would be
shown a stale risk level presented as current. There is exactly one place a
risk level lives, and the transcript points at it rather than duplicating it.

`user_id` is denormalised alongside `job_id` so ownership can be checked
without a join, matching how every other route scopes access.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ChatMessage(Base):
    """One message in a job's conversation transcript."""

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False, index=True
    )
    # "user" | "assistant"
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    # "text" | "risk_card" — a risk_card row is a positional placeholder whose
    # content is rendered from the assessment at read time (see docstring).
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Explicit ordering: a batch of messages is written in one request and
    # created_at alone can tie at that resolution, which would let a
    # transcript render out of order — the one thing storing it must get right.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
