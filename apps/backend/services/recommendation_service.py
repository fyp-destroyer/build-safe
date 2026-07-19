"""Placeholder tool/material recommendation, gated on risk_level.

The real catalog-backed recommendation engine is `ai/recommend/` (Phase 6,
architecture.md §3/§4) — not implemented here. This only proves the
endpoint shape and the risk-level gating (GET /recommendations/{job_id}
requires a completed assessment).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import ApiError
from models import Job, RiskAssessment
from schemas.recommendation import RecommendationsOut, RecommendedItem


async def get_recommendations(db: AsyncSession, job: Job) -> RecommendationsOut:
    """Return placeholder recommendations for a job's completed assessment.

    Raises ApiError(409) if no completed assessment exists yet.
    """
    result = await db.execute(select(RiskAssessment).where(RiskAssessment.job_id == job.id))
    assessment = result.scalar_one_or_none()

    if assessment is None or assessment.status != "completed":
        raise ApiError(
            409,
            "assessment_not_completed",
            "Recommendations require a completed risk assessment.",
        )

    items = _placeholder_items(assessment.risk_level)
    return RecommendationsOut(job_id=job.id, risk_level=assessment.risk_level, items=items)


def _placeholder_items(risk_level: int) -> list[RecommendedItem]:
    """Fixed placeholder list, gated only on risk_level. Not a real catalog
    lookup — every category/task gets the same generic items."""
    items = [
        RecommendedItem(
            name="Safety glasses",
            category="ppe",
            required=risk_level >= 2,
            note="Placeholder recommendation — real catalog not implemented (Phase 6).",
        ),
        RecommendedItem(
            name="Work gloves",
            category="ppe",
            required=risk_level >= 2,
            note="Placeholder recommendation — real catalog not implemented (Phase 6).",
        ),
    ]
    if risk_level >= 3:
        items.append(
            RecommendedItem(
                name="Licensed professional consultation",
                category="service",
                required=True,
                note="Risk level indicates this task should involve a professional.",
            )
        )
    if risk_level >= 4:
        items.append(
            RecommendedItem(
                name="Do not proceed without professional isolation/inspection",
                category="warning",
                required=True,
                note="Placeholder — real guidance text is templated from ai/explanation in a"
                " later phase.",
            )
        )
    return items
