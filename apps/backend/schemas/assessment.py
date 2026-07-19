"""Pydantic v2 request/response schemas for /assessments."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RiskAssessmentOut(BaseModel):
    """GET /assessments/{job_id} response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    risk_level: int = Field(ge=1, le=5)
    confidence: float
    explanation: str
    hazard_tags: list[str]
    triggered_rules: list[str]
    cost: str | None
    time: str | None
    difficulty: str | None
    status: str
    created_at: datetime
