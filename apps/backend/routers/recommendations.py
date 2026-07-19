"""Recommendations router — tools/materials/PPE recommendations.

Placeholder logic in services/recommendation_service.py; real logic lives
in ai/recommend/ (Phase 6). Ownership-scoped; 409 if assessment isn't
completed yet.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.security import get_current_user
from models import User
from schemas.recommendation import RecommendationsOut
from services import job_service, recommendation_service

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/{job_id}", response_model=RecommendationsOut)
async def get_recommendations(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecommendationsOut:
    job = await job_service.get_owned_job(db, job_id, current_user.id)
    return await recommendation_service.get_recommendations(db, job)
