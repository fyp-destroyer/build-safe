"""RiskAssessment model — srs.md §6.1 `risk_assessments` table.

One assessment per job for now (`job_id` is unique) — re-assessment/history
of multiple assessments per job is out of scope for this pass.

`cost`, `time`, `difficulty` are nullable string placeholders: the real
cost/time estimator is `ai/recommend/` (Phase 6), not implemented yet.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class RiskAssessment(Base):
    """Output of the classification engine for a single job."""

    __tablename__ = "risk_assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False, unique=True, index=True
    )
    risk_level: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    hazard_tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    triggered_rules: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    cost: Mapped[str | None] = mapped_column(String(100), nullable=True)
    time: Mapped[str | None] = mapped_column(String(100), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped["Job"] = relationship(back_populates="risk_assessment")  # noqa: F821
