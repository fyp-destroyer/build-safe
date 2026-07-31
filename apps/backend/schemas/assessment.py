"""Pydantic v2 request/response schemas for /assessments."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field


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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def safety_notes(self) -> list[str]:
        """Plain-language guidance for each triggered rule (FR-05).

        Derived at read time from `triggered_rules` via the rule engine's
        hardcoded explanation text - not persisted, so the wording stays in
        one place (ai/rule_engine/catalog.py) and improves for existing
        assessments when the catalog does.

        Without this the UI can only show the rule id, which is what it did
        before: a user reporting a gas smell was shown "Active gas or co"
        rather than "leave the area, avoid switches and naked flames, and
        contact your gas emergency service". The text is deliberately
        hardcoded, never LLM-generated (rules.md 4).
        """
        from ai.rule_engine import explain

        return explain(list(self.triggered_rules))

    cost: str | None
    time: str | None
    difficulty: str | None
    status: str
    created_at: datetime
