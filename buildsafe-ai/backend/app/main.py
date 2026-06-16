from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import AssessmentRequest, AssessmentResponse
from app.services.followup_engine import get_follow_up_questions
from app.services.recommendation_engine import get_recommendations
from app.services.risk_engine import assess_risk

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
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "buildsafe-ai-api"}


@app.post("/api/assess-task", response_model=AssessmentResponse)
def assess_task(payload: AssessmentRequest) -> AssessmentResponse:
    risk_result = assess_risk(payload)
    category_key = risk_result.pop("category_key")
    recommendations = get_recommendations(category_key, risk_result["risk_level"])
    follow_up_questions = get_follow_up_questions(category_key, payload.answers_to_followups)

    return AssessmentResponse(
        **risk_result,
        follow_up_questions=follow_up_questions,
        **recommendations,
    )
