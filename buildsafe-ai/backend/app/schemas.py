from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

SkillLevel = Literal["beginner", "intermediate", "expert"]
LocationType = Literal["house", "apartment", "shop", "office"]
Urgency = Literal["low", "medium", "high", "emergency"]
RiskLevel = Literal[
    "Safe DIY",
    "DIY with supervision",
    "Professional recommended",
    "Professional required",
    "Dangerous / permit-required / do not attempt",
]
TaskIntent = Literal[
    "hanging_wall_decor",
    "wall_painting",
    "electrical_fixture_installation",
    "electrical_wiring_repair",
    "plumbing_leak_repair",
    "wall_demolition",
    "tile_installation",
    "furniture_assembly",
    "shelf_installation",
    "light_bulb_replacement",
    "ceiling_fan_installation",
    "hvac_repair",
    "general_diy",
]
PlanType = Literal[
    "safe_diy_plan",
    "supervised_plan",
    "preparation_checklist",
    "professional_only_checklist",
]


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


class ActionPlanRequest(BaseModel):
    task_description: str = Field(..., min_length=3, max_length=300)
    task_intent: TaskIntent
    task_category: str = Field(..., min_length=1, max_length=120)
    risk_level: RiskLevel
    risk_score: int = Field(..., ge=0, le=100)
    user_skill_level: SkillLevel = Field(default="beginner")
    available_tools: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    required_materials: list[str] = Field(default_factory=list)
    required_ppe: list[str] = Field(default_factory=list)
    safety_warnings: list[str] = Field(default_factory=list)
    recommended_professional_category: str = Field(default="", max_length=160)
    followup_answers: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task_description", "task_category", "recommended_professional_category")
    @classmethod
    def trim_action_plan_text_fields(cls, value: str) -> str:
        return " ".join(value.strip().split())

    @field_validator(
        "available_tools",
        "required_tools",
        "required_materials",
        "required_ppe",
        "safety_warnings",
    )
    @classmethod
    def clean_action_plan_lists(cls, values: list[str]) -> list[str]:
        if len(values) > 40:
            raise ValueError("Action plan lists can include at most 40 items")
        cleaned = [" ".join(value.strip().split()) for value in values if value.strip()]
        return list(dict.fromkeys(cleaned))

    @field_validator("followup_answers")
    @classmethod
    def limit_action_plan_followup_answers(cls, answers: dict[str, Any]) -> dict[str, Any]:
        if len(answers) > 30:
            raise ValueError("followup_answers can include at most 30 answers")
        return answers


class ActionPlanStep(BaseModel):
    step_number: int
    title: str
    description: str
    safety_note: str
    estimated_time: str


class ActionPlanDebugTrace(BaseModel):
    action_plan_generated: bool = True
    plan_type: PlanType
    llm_used_for_plan: bool = False
    safety_restriction_applied: bool = False
    reason_if_steps_blocked: str = ""


class ActionPlanResponse(BaseModel):
    plan_type: PlanType
    allowed_to_show_steps: bool
    title: str
    summary: str
    safety_notice: str
    prerequisites: list[str]
    tools_required: list[str]
    materials_required: list[str]
    ppe_required: list[str]
    steps: list[ActionPlanStep]
    stop_conditions: list[str]
    when_to_call_professional: list[str]
    professional_questions: list[str]
    disclaimer: str
    debug_trace: ActionPlanDebugTrace | None = None


class RiskScoreComponent(BaseModel):
    points: int
    max: int
    reason: str


class RiskScoreBreakdown(BaseModel):
    base_task_risk: RiskScoreComponent
    hazard_severity: RiskScoreComponent
    skill_mismatch: RiskScoreComponent
    tools_ppe_readiness: RiskScoreComponent
    environment_urgency_unknowns: RiskScoreComponent
    total: int
    threshold_label: RiskLevel
    safety_overrides_applied: list[str] = Field(default_factory=list)


class AssessmentResponse(BaseModel):
    task_intent: TaskIntent
    task_category: str
    risk_level: RiskLevel
    risk_score: int
    risk_score_breakdown: RiskScoreBreakdown
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
    debug_trace: DebugTrace | None = None


class UpdateAssessmentRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=120)
    previous_assessment: dict[str, Any]
    task_description: str = Field(..., min_length=3, max_length=300)
    task_intent: str = Field(..., min_length=1, max_length=120)
    task_category: str = Field(..., min_length=1, max_length=120)
    previous_answers: dict[str, Any]
    update_message: str = Field(..., min_length=1, max_length=500)
    current_user_context: dict[str, Any]

    @field_validator(
        "session_id",
        "task_description",
        "task_intent",
        "task_category",
        "update_message",
    )
    @classmethod
    def trim_update_text_fields(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("Field cannot be empty")
        return cleaned

    @field_validator("previous_answers")
    @classmethod
    def limit_previous_answers(cls, answers: dict[str, Any]) -> dict[str, Any]:
        if len(answers) > 50:
            raise ValueError("previous_answers can include at most 50 answers")
        return answers

    @field_validator("current_user_context")
    @classmethod
    def limit_current_user_context(cls, context: dict[str, Any]) -> dict[str, Any]:
        if len(context) > 50:
            raise ValueError("current_user_context can include at most 50 fields")
        return context


class DetectedAssessmentUpdate(BaseModel):
    field: str
    old_value_if_known: Any | None = None
    new_value: Any
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class UpdateAssessmentChangeSummary(BaseModel):
    detected_updates: list[DetectedAssessmentUpdate] = Field(default_factory=list)
    affected_sections: list[str] = Field(default_factory=list)
    likely_unchanged_sections: list[str] = Field(default_factory=list)
    changed_sections: list[str] = Field(default_factory=list)
    unchanged_sections: list[str] = Field(default_factory=list)
    risk_score_change: dict[str, Any] | None = None
    risk_level_change: dict[str, Any] | None = None


class UpdateAssessmentDebugTrace(BaseModel):
    update_flow_used: bool = True
    update_message: str
    update_parsing_enabled: bool = True
    gemini_enabled: bool = False
    gemini_used: bool = False
    fallback_used: bool = True
    parser_source: str = "fallback"
    gemini_model: str = ""
    gemini_error: str | None = None


class UpdateAssessmentResponse(BaseModel):
    updated_assessment: dict[str, Any]
    change_summary: UpdateAssessmentChangeSummary
    assistant_message: str
    needs_reassessment: bool = False
    requires_more_information: bool = False
    follow_up_questions: list[str] = Field(default_factory=list)
    debug_trace: UpdateAssessmentDebugTrace


class SeedDataResponse(BaseModel):
    tools: dict[str, list[str]]
    materials: dict[str, dict[str, list[str]]]
    safety_rules: list[dict[str, Any]]
    professional_categories: dict[str, dict[str, str]]


class FollowupPlanRequest(BaseModel):
    task_description: str = Field(..., min_length=3, max_length=300)
    known_answers: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task_description")
    @classmethod
    def trim_task_description(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("Field cannot be empty")
        return cleaned

    @field_validator("known_answers")
    @classmethod
    def limit_known_answers(cls, answers: dict[str, Any]) -> dict[str, Any]:
        if len(answers) > 30:
            raise ValueError("known_answers can include at most 30 answers")
        return answers


class FollowupPlanResponse(BaseModel):
    task_intent: TaskIntent
    task_category: str
    is_ambiguous: bool = False
    possible_interpretations: list[str] = Field(default_factory=list)
    selected_interpretation: str = ""
    risk_factors: list[str]
    critical_missing_info: list[str]
    follow_up_questions: list[str]
    suggested_risk_level: RiskLevel
    short_reason: str
    llm_used: bool = False
    debug_trace: DebugTrace | None = None


class DebugTrace(BaseModel):
    gemini_enabled: bool
    gemini_used: bool
    gemini_model: str
    gemini_used_for: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    detected_task_intent: TaskIntent | None = None
    detected_task_category: str | None = None
    llm_suggested_risk_level: RiskLevel | None = None
    rule_engine_risk_level: RiskLevel | None = None
    final_risk_level: RiskLevel | None = None
    rules_triggered: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    critical_missing_info: list[str] = Field(default_factory=list)
    selected_interpretation: str = ""
    notes: list[str] = Field(default_factory=list)
    gemini_error: str | None = None
    parsed_llm_response: dict[str, Any] | None = None
    llm_response_text: str | None = None
    llm_prompt: str | None = None
