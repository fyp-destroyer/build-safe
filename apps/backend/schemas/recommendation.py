"""Pydantic v2 request/response schemas for /recommendations.

Placeholder shape — the real catalog-backed recommendation engine is
`ai/recommend/` (Phase 6), not implemented in this pass. See
services/recommendation_service.py.
"""

from uuid import UUID

from pydantic import BaseModel


class RecommendedItem(BaseModel):
    """A single placeholder tool/material/PPE recommendation."""

    name: str
    category: str
    required: bool
    note: str


class RecommendationsOut(BaseModel):
    """GET /recommendations/{job_id} response."""

    job_id: UUID
    risk_level: int
    items: list[RecommendedItem]
    is_placeholder: bool = True
