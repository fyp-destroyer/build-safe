"""Job model — srs.md §6.1 `jobs` table (minimum viable subset).

`category` is a plain string constrained at the schema layer to the 9
categories locked in phases.md Phase 1 (electrical, plumbing, carpentry,
masonry, painting, tiling, HVAC, roofing, general) rather than a separate
`task_categories` table — that table is out of scope for this pass.

`followup_answers` is free-form JSON until Phase 5 defines the real
follow-up question schema per category.

`status` is a plain string rather than a DB enum for now:
  "pending_followup" | "ready_to_assess" | "assessed" | "failed"
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class Job(Base):
    """A user-submitted DIY/construction task and its context."""

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    skill_level: Mapped[str] = mapped_column(String(50), nullable=False)
    # Nullable since 2026-07-31: the chat flow no longer asks for it and
    # nothing reads it. Column kept rather than dropped so existing rows
    # survive and the change is reversible.
    urgency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    followup_answers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Catalog rule ids the LLM tagger proposed for this description, resolved
    # ONCE at creation and reused for the rest of the job's life. Persisted
    # because the follow-up gate and the rule engine must see the identical
    # hazard set: tagging separately at each step let assessment escalate on a
    # hazard the intake flow never knew about, so the user was penalised for
    # not answering a question that was never asked (see job_service).
    # NULL means "not tagged yet" (LLM unavailable at creation), which is
    # distinct from [] meaning "tagged, no hazards found".
    llm_hazard_ids: Mapped[list | None] = mapped_column(JSON, nullable=True, default=None)
    # Follow-up fields the tagger asked for because the description was
    # ambiguous about them (e.g. "change a light bulb" says nothing about
    # height). Unioned into the catalog-derived set, never subtracted from
    # it. Persisted alongside llm_hazard_ids and for the same reason: the set
    # of questions the user is ASKED must match the set assessment scores
    # against, or a job escalates on a field nobody was shown.
    llm_followup_fields: Mapped[list | None] = mapped_column(JSON, nullable=True, default=None)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_followup")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="jobs")  # noqa: F821
    risk_assessment: Mapped["RiskAssessment | None"] = relationship(  # noqa: F821
        back_populates="job", uselist=False
    )
