"""An AI pipeline failure during assess must write an ai_logs row and mark
the job/assessment "failed" rather than silently succeeding with a "safe"
result (CLAUDE.md / rules.md §4 points 3 and 6).
"""

from unittest.mock import patch

import pytest
from sqlalchemy import select

from models import AiLog, Job, RiskAssessment
from tests.conftest import register_and_login

pytestmark = pytest.mark.anyio


async def test_classifier_exception_writes_failed_assessment_and_ai_log(client, db_session):
    token = await register_and_login(client, "failure_case@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await client.post(
        "/jobs",
        json={
            "description": "paint the shed",
            "category": "painting",
            "skill_level": "beginner",
            "urgency": "low",
        },
        headers=headers,
    )
    job_id = create_resp.json()["id"]

    with patch(
        "services.job_service.classify",
        side_effect=RuntimeError("simulated classifier crash"),
    ):
        assess_resp = await client.post(f"/jobs/{job_id}/assess", headers=headers)

    # The route itself must not silently report success.
    assert assess_resp.status_code == 200
    body = assess_resp.json()
    assert body["status"] == "failed"

    # Job row reflects the failure.
    job_row = (await db_session.execute(select(Job).where(Job.id == job_id))).scalar_one()
    assert job_row.status == "failed"

    # RiskAssessment row is marked failed, not "completed", and never
    # silently defaults to a low/safe risk level.
    assessment_row = (
        await db_session.execute(select(RiskAssessment).where(RiskAssessment.job_id == job_id))
    ).scalar_one()
    assert assessment_row.status == "failed"
    assert assessment_row.risk_level == 5  # worst plausible case, never "safe"

    # An ai_logs row exists for this attempt with the failure captured —
    # every classification is logged, no sampling, even on failure.
    ai_log_row = (
        await db_session.execute(select(AiLog).where(AiLog.job_id == job_id))
    ).scalar_one()
    assert ai_log_row.model_output.get("error_type") == "RuntimeError"
    assert "simulated classifier crash" in ai_log_row.model_output.get("error", "")


async def test_recommendations_blocked_when_assessment_failed(client, db_session):
    """A 409 (not a fabricated recommendation list) when the assessment
    didn't complete successfully."""
    token = await register_and_login(client, "failure_case2@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await client.post(
        "/jobs",
        json={
            "description": "paint the deck",
            "category": "painting",
            "skill_level": "beginner",
            "urgency": "low",
        },
        headers=headers,
    )
    job_id = create_resp.json()["id"]

    with patch(
        "services.job_service.evaluate",
        side_effect=RuntimeError("simulated rule engine crash"),
    ):
        await client.post(f"/jobs/{job_id}/assess", headers=headers)

    resp = await client.get(f"/recommendations/{job_id}", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "assessment_not_completed"
