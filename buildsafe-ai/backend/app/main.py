from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.schemas import (
    ActionPlanRequest,
    ActionPlanResponse,
    AssessmentRequest,
    AssessmentResponse,
    FollowupPlanRequest,
    FollowupPlanResponse,
    SeedDataResponse,
    UpdateAssessmentChangeSummary,
    UpdateAssessmentDebugTrace,
    UpdateAssessmentRequest,
    UpdateAssessmentResponse,
)
from app.services.action_plan_engine import generate_action_plan
from app.services.assessment_update_engine import process_assessment_update
from app.services.followup_engine import get_follow_up_questions
from app.services.llm_service import plan_followups
from app.services.recommendation_engine import (
    get_recommendations,
    validate_assessment_consistency,
)
from app.services.risk_engine import assess_risk
from app.services.seed_data import get_seed_data

app = FastAPI(
    title="BuildSafe AI API",
    description="Risk-aware DIY and construction task assessment API.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "message": "Invalid assessment input",
            "details": exc.errors(),
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "buildsafe-ai-api"}


# TODO: Photo upload.
# Add a multipart endpoint that stores task photos, extracts observable hazards,
# and passes image-derived signals into the risk engine.
@app.post("/api/assess-task", response_model=AssessmentResponse)
def assess_task(payload: AssessmentRequest) -> AssessmentResponse:
    llm_analysis = plan_followups(payload.task_description, payload.answers_to_followups)
    risk_result = assess_risk(payload, llm_analysis=llm_analysis)
    category_key = risk_result.pop("category_key")
    recommendations = get_recommendations(
        category_key,
        risk_result["risk_level"],
        risk_result["task_intent"],
    )
    consistency_checked = validate_assessment_consistency(
        task_intent=risk_result["task_intent"],
        explanation=risk_result["explanation"],
        recommendations=recommendations,
        selected_interpretation=llm_analysis.selected_interpretation,
        risk_level=risk_result["risk_level"],
    )
    follow_up_questions = (
        llm_analysis.critical_missing_info[:2]
        if llm_analysis.critical_missing_info and payload.answers_to_followups
        else get_follow_up_questions(
            risk_result["task_intent"],
            category_key,
            payload.answers_to_followups,
        )
    )
    debug_trace = None
    if llm_analysis.debug_trace is not None:
        gemini_used_for = list(llm_analysis.debug_trace.gemini_used_for)
        if llm_analysis.llm_used and "explanation_assistance" not in gemini_used_for:
            gemini_used_for.append("explanation_assistance")

        debug_notes = list(llm_analysis.debug_trace.notes)
        debug_notes.append("The rule engine kept final authority over the selected risk level.")
        if llm_analysis.debug_trace.fallback_used:
            debug_notes.append("Assessment proceeded with deterministic fallback outputs.")

        debug_trace = llm_analysis.debug_trace.model_copy(
            update={
                "gemini_used_for": gemini_used_for,
                "detected_task_intent": risk_result["task_intent"],
                "detected_task_category": category_key,
                "rule_engine_risk_level": risk_result["risk_level"],
                "final_risk_level": risk_result["risk_level"],
                "rules_triggered": risk_result["rules_triggered"],
                "follow_up_questions": follow_up_questions,
                "notes": list(dict.fromkeys(debug_notes)),
            }
        )
    risk_result["explanation"] = consistency_checked["explanation"]

    return AssessmentResponse(
        **risk_result,
        follow_up_questions=follow_up_questions,
        required_tools=consistency_checked["required_tools"],
        required_materials=consistency_checked["required_materials"],
        required_ppe=consistency_checked["required_ppe"],
        estimated_time=consistency_checked["estimated_time"],
        estimated_cost_range=consistency_checked["estimated_cost_range"],
        recommended_professional_category=consistency_checked["recommended_professional_category"],
        debug_trace=debug_trace,
    )


@app.post("/api/llm/plan-followups", response_model=FollowupPlanResponse)
def plan_task_followups(payload: FollowupPlanRequest) -> FollowupPlanResponse:
    return plan_followups(payload.task_description, payload.known_answers)


@app.post("/api/action-plan", response_model=ActionPlanResponse)
def create_action_plan(payload: ActionPlanRequest) -> ActionPlanResponse:
    return generate_action_plan(payload)


@app.post("/api/update-assessment", response_model=UpdateAssessmentResponse)
def update_assessment(payload: UpdateAssessmentRequest) -> UpdateAssessmentResponse:
    update_result = process_assessment_update(
        previous_assessment=payload.previous_assessment,
        task_description=payload.task_description,
        task_intent=payload.task_intent,
        task_category=payload.task_category,
        previous_answers=payload.previous_answers,
        update_message=payload.update_message,
        current_user_context=payload.current_user_context,
    )

    return UpdateAssessmentResponse(
        updated_assessment=update_result.updated_assessment,
        change_summary=UpdateAssessmentChangeSummary(
            detected_updates=update_result.detected_updates,
            affected_sections=update_result.affected_sections,
            likely_unchanged_sections=update_result.likely_unchanged_sections,
            changed_sections=update_result.changed_sections,
            unchanged_sections=update_result.unchanged_sections,
            risk_score_change=update_result.risk_score_change,
            risk_level_change=update_result.risk_level_change,
        ),
        assistant_message=update_result.assistant_message,
        needs_reassessment=update_result.needs_reassessment,
        requires_more_information=update_result.requires_more_information,
        follow_up_questions=update_result.follow_up_questions,
        debug_trace=UpdateAssessmentDebugTrace(
            update_flow_used=True,
            update_message=payload.update_message,
            update_parsing_enabled=True,
            gemini_enabled=update_result.gemini_enabled,
            gemini_used=update_result.gemini_used,
            fallback_used=update_result.fallback_used,
            parser_source=update_result.parser_source,
            gemini_model=update_result.gemini_model,
            gemini_error=update_result.gemini_error,
        ),
    )


@app.get("/api/admin/seed-data", response_model=SeedDataResponse)
def read_seed_data() -> SeedDataResponse:
    return SeedDataResponse(**get_seed_data())
