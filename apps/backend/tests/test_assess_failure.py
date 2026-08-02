"""An AI pipeline failure during assess must write an ai_logs row and mark
the job/assessment "failed" rather than silently succeeding with a "safe"
result (CLAUDE.md / rules.md §4 points 3 and 6).
"""

from unittest.mock import patch

import pytest
from sqlalchemy import select

from models import AiLog, Job, RiskAssessment
from tests.conftest import register_and_login, set_risk_pipeline

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


async def test_rules_only_mode_ignores_the_classifier_but_still_logs_it(
    client, db_session, monkeypatch
):
    """RISK_USE_ML_CLASSIFIER=false -> final_risk = rule_risk.

    The classifier still runs and its prediction is still recorded, so the
    decision stays auditable and the flag is one env var away from being
    reverted. What must NOT happen is the classifier quietly steering a
    result it is supposed to be excluded from.
    """
    set_risk_pipeline(monkeypatch, use_ml=False)
    token = await register_and_login(client, "rules_only@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await client.post(
        "/jobs",
        json={
            "description": "paint the shed",
            "category": "painting",
            "skill_level": "Beginner",
        },
        headers=headers,
    )
    job_id = create_resp.json()["id"]

    # A classifier screaming level 5 at a task no rule matches must not move
    # the result: rules say 1, and rules are the only vote being counted.
    with patch("services.job_service.classify", return_value=(5, 0.99)):
        assess_resp = await client.post(f"/jobs/{job_id}/assess", headers=headers)

    assert assess_resp.status_code == 200
    body = assess_resp.json()
    assert body["status"] == "completed"
    assert body["risk_level"] == 1, "rules-only mode let the classifier decide"

    log = (await db_session.execute(select(AiLog).where(AiLog.job_id == job_id))).scalar_one()
    assert log.model_output["ml_risk"] == 5, "the prediction must still be recorded"
    assert log.model_output["rule_risk"] == 1
    assert log.model_output["final_risk"] == 1
    assert log.model_output["ml_used"] is False

    # The user-facing text must not cite a classifier that had no say.
    assessment = (
        await db_session.execute(select(RiskAssessment).where(RiskAssessment.job_id == job_id))
    ).scalar_one()
    assert "Classifier predicted" not in assessment.explanation


async def test_rules_only_mode_still_escalates_on_hazards(client, monkeypatch):
    """Turning the classifier off must not weaken the rule engine itself."""
    set_risk_pipeline(monkeypatch, use_ml=False)
    token = await register_and_login(client, "rules_only_gas@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await client.post(
        "/jobs",
        json={
            "description": "I can smell gas near the cooker connection",
            "category": "plumbing",
            "skill_level": "Beginner",
        },
        headers=headers,
    )
    job_id = create_resp.json()["id"]

    with patch("services.job_service.classify", return_value=(1, 0.9)):
        assess_resp = await client.post(f"/jobs/{job_id}/assess", headers=headers)

    assert assess_resp.json()["risk_level"] == 5


async def test_rules_only_mode_survives_a_broken_classifier(client, db_session, monkeypatch):
    """A classifier that has no vote cannot invalidate the assessment.

    The fail-loud rule (CLAUDE.md) exists because a missing ML term would
    otherwise silently lower the result. In rules-only mode it cannot lower
    anything — it was never counted — so the assessment completes on the
    rule engine, and the error is recorded rather than swallowed.
    """
    set_risk_pipeline(monkeypatch, use_ml=False)
    token = await register_and_login(client, "rules_only_broken@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await client.post(
        "/jobs",
        json={
            "description": "walk across the fragile perspex roof panels",
            "category": "roofing",
            "skill_level": "Beginner",
        },
        headers=headers,
    )
    job_id = create_resp.json()["id"]

    with patch(
        "services.job_service.classify",
        side_effect=RuntimeError("simulated classifier crash"),
    ):
        assess_resp = await client.post(f"/jobs/{job_id}/assess", headers=headers)

    body = assess_resp.json()
    assert body["status"] == "completed"
    assert body["risk_level"] == 5  # the rule engine still did its job

    log = (await db_session.execute(select(AiLog).where(AiLog.job_id == job_id))).scalar_one()
    assert "simulated classifier crash" in log.model_output.get("ml_error", "")
    assert log.model_output["ml_used"] is False


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
