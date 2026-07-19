"""Integration coverage for the Gemini-assisted job flow:
  - POST /jobs with `category` omitted -> inferred category from the fixed set
  - next_followup surfaced on create/submit_followup, phrased via Gemini
  - GET /jobs list endpoint (ownership isolation, most-recent-first order)

Mocks `ai.rule_engine.llm_assist.generate_structured` throughout — no real
network call to Gemini is made, matching every other AI-pipeline test in
this suite (see test_assess_failure.py's pattern of patching at the
service-boundary import site).
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import update

from ai.rule_engine.llm_assist import CategoryTag, PhrasedQuestion
from models import Job
from schemas.job import TASK_CATEGORIES
from tests.conftest import register_and_login

pytestmark = pytest.mark.anyio


async def _auth_headers(client, email: str) -> dict:
    token = await register_and_login(client, email)
    return {"Authorization": f"Bearer {token}"}


def _llm_stub(prompt: str, response_schema):
    """generate_structured is called for both category tagging and
    follow-up phrasing within a single request (e.g. a carpentry job needs
    both) — a real Gemini call would naturally return the shape asked for,
    so the stub mirrors that by dispatching on the requested schema rather
    than returning one canned value for every call."""
    if response_schema is CategoryTag:
        return CategoryTag(category="carpentry")
    return PhrasedQuestion(question="Have you confirmed this wall is not load-bearing?")


async def test_create_job_without_category_infers_from_fixed_set(client):
    """category omitted from the request body -> Gemini tagging call ->
    stored category is still one of the fixed 9 values."""
    headers = await _auth_headers(client, "llm_job1@example.com")

    with patch("ai.rule_engine.llm_assist.generate_structured", side_effect=_llm_stub):
        resp = await client.post(
            "/jobs",
            json={
                "description": "build a bookshelf from plywood",
                "skill_level": "intermediate",
                "urgency": "low",
            },
            headers=headers,
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["category"] == "carpentry"
    assert body["category"] in TASK_CATEGORIES


async def test_electrical_job_next_followup_then_clears_after_answer(client):
    """Creating an electrical job with power_isolated missing surfaces a
    next_followup with the right field and Gemini-phrased (mocked) question
    text; answering it clears next_followup and flips status."""
    headers = await _auth_headers(client, "llm_job2@example.com")

    phrased = PhrasedQuestion(question="Have you switched off the breaker for this circuit?")
    with patch("ai.rule_engine.llm_assist.generate_structured", return_value=phrased):
        create_resp = await client.post(
            "/jobs",
            json={
                "description": "replace a light switch",
                "category": "electrical",
                "skill_level": "beginner",
                "urgency": "medium",
            },
            headers=headers,
        )
        assert create_resp.status_code == 201
        body = create_resp.json()
        assert body["next_followup"] is not None
        assert body["next_followup"]["field"] == "power_isolated"
        assert body["next_followup"]["question"].strip()

        job_id = body["id"]

        followup_resp = await client.patch(
            f"/jobs/{job_id}/followup",
            json={"answers": {"power_isolated": True}},
            headers=headers,
        )

    assert followup_resp.status_code == 200
    followup_body = followup_resp.json()
    assert followup_body["next_followup"] is None
    assert followup_body["status"] == "ready_to_assess"


async def test_list_jobs_returns_only_callers_jobs_most_recent_first(client, db_session):
    """Two different users' jobs must never cross-leak, and the caller's own
    jobs come back most-recent-first.

    The whole test runs inside one wrapped DB transaction (see
    conftest.py's `db_session` fixture), and Postgres `now()` is fixed for
    the lifetime of a transaction — so jobs created back-to-back here would
    otherwise get identical `created_at` values regardless of insertion
    order. To actually exercise the ORDER BY clause (rather than relying on
    a real wall-clock gap that wouldn't exist in this test setup), the
    timestamps are set explicitly here before asserting on order.
    """
    headers_a = await _auth_headers(client, "llm_list_a@example.com")
    headers_b = await _auth_headers(client, "llm_list_b@example.com")

    async def _create(headers, description):
        resp = await client.post(
            "/jobs",
            json={
                "description": description,
                "category": "painting",
                "skill_level": "beginner",
                "urgency": "low",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    job_a1 = await _create(headers_a, "paint the fence")
    job_a2 = await _create(headers_a, "paint the shed")
    await _create(headers_b, "paint user b's garage")

    now = datetime.now(timezone.utc)
    await db_session.execute(
        update(Job).where(Job.id == job_a1).values(created_at=now - timedelta(minutes=5))
    )
    await db_session.execute(update(Job).where(Job.id == job_a2).values(created_at=now))
    await db_session.commit()

    resp = await client.get("/jobs", headers=headers_a)
    assert resp.status_code == 200
    jobs = resp.json()

    returned_ids = [job["id"] for job in jobs]
    assert len(jobs) == 2  # user A must not see user B's job

    # Most recent first.
    assert returned_ids[0] == job_a2
    assert returned_ids[1] == job_a1

    for job in jobs:
        assert "next_followup" in job
