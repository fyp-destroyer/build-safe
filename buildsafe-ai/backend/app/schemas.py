from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AssessmentRequest(BaseModel):
    task_description: str = Field(..., min_length=3)
    user_skill_level: str = Field(default="beginner")
    available_tools: list[str] = Field(default_factory=list)
    location_type: str = Field(default="house")
    urgency: str = Field(default="low")
    budget_range: str = Field(default="not specified")
    answers_to_followups: dict[str, Any] = Field(default_factory=dict)


class AssessmentResponse(BaseModel):
    task_category: str
    risk_level: str
    risk_score: int
    confidence_score: float
    explanation: str
    follow_up_questions: list[str]
    required_tools: list[str]
    required_materials: list[str]
    required_ppe: list[str]
    estimated_time: str
    estimated_cost_range: str
    recommended_professional_category: str
    safety_warnings: list[str]
    rules_triggered: list[str]
