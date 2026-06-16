from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

SkillLevel = Literal["beginner", "intermediate", "expert"]
LocationType = Literal["house", "apartment", "shop", "office"]
Urgency = Literal["low", "medium", "high", "emergency"]


class AssessmentRequest(BaseModel):
    task_description: str = Field(..., min_length=3, max_length=300)
    user_skill_level: SkillLevel = Field(default="beginner")
    available_tools: list[str] = Field(default_factory=list)
    location_type: LocationType = Field(default="house")
    urgency: Urgency = Field(default="low")
    budget_range: str = Field(default="not specified", max_length=80)
    answers_to_followups: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task_description", "budget_range")
    @classmethod
    def trim_text_fields(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("Field cannot be empty")
        return cleaned

    @field_validator("available_tools")
    @classmethod
    def clean_available_tools(cls, tools: list[str]) -> list[str]:
        if len(tools) > 25:
            raise ValueError("available_tools can include at most 25 items")
        cleaned = [" ".join(tool.strip().split()) for tool in tools if tool.strip()]
        return list(dict.fromkeys(cleaned))

    @field_validator("answers_to_followups")
    @classmethod
    def limit_followup_answers(cls, answers: dict[str, Any]) -> dict[str, Any]:
        if len(answers) > 30:
            raise ValueError("answers_to_followups can include at most 30 answers")
        return answers


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


class SeedDataResponse(BaseModel):
    tools: dict[str, list[str]]
    materials: dict[str, dict[str, list[str]]]
    safety_rules: list[dict[str, Any]]
    professional_categories: dict[str, dict[str, str]]
