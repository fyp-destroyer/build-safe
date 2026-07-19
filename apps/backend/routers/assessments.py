"""Assessments router — risk classification results (architecture.md §4
step 5): GET /assessments/{job_id}.

Ownership-scoped (404 if not owner, never leaks existence). 404 if no
assessment exists yet for an owned job.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.errors import ApiError
from core.security import get_current_user
from models import RiskAssessment, User
from schemas.assessment import RiskAssessmentOut
from services import job_service

router = APIRouter(prefix="/assessments", tags=["assessments"])


@router.get("/{job_id}", response_model=RiskAssessmentOut)
async def get_assessment(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RiskAssessmentOut:
    job = await job_service.get_owned_job(db, job_id, current_user.id)

    result = await db.execute(select(RiskAssessment).where(RiskAssessment.job_id == job.id))
    assessment = result.scalar_one_or_none()
    if assessment is None:
        raise ApiError(404, "assessment_not_found", "No assessment exists for this job yet.")

    return assessment
