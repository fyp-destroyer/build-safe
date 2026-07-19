"""AiLog model — srs.md §6.1 `ai_logs` table.

Written on EVERY assessment attempt, including failures (CLAUDE.md: "AI
pipeline failures must set assessment_status = 'failed' ... never silently
fall back"). No sampling — rules.md §4 point 6.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class AiLog(Base):
    """Auditable record of one classifier/rule-engine invocation."""

    __tablename__ = "ai_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False, index=True
    )
    model_input: Mapped[dict] = mapped_column(JSON, nullable=False)
    model_output: Mapped[dict] = mapped_column(JSON, nullable=False)
    triggered_rules: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
