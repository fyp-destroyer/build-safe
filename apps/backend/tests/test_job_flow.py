"""Job create -> followup -> assess happy path, producing a risk_assessments
row. Also covers ownership 404s and the 409 when follow-ups are incomplete.
"""

import pytest

from tests.conftest import register_and_login

pytestmark = pytest.mark.anyio


async def _auth_headers(client, email: str) -> dict:
    token = await register_and_login(client, email)
    return {"Authorization": f"Bearer {token}"}


async def test_create_job_with_no_required_followups_starts_ready_to_assess(client):
    """Painting has no safety-critical follow-up fields in the placeholder
    mapping, so create_job should apply the same status-transition logic
    submit_followup does and start it at "ready_to_assess" immediately,
    rather than a misleading "pending_followup" with next_followup already
    null."""
    headers = await _auth_headers(client, "job1@example.com")
    resp = await client.post(
        "/jobs",
        json={
            "description": "paint the living room walls",
            "category": "painting",
            "skill_level": "beginner",
            "urgency": "low",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "ready_to_assess"
    assert body["category"] == "painting"
    assert body["next_followup"] is None


async def test_create_job_with_required_followups_starts_pending_followup(client):
    headers = await _auth_headers(client, "job1b@example.com")
    resp = await client.post(
        "/jobs",
        json={
            "description": "replace a light switch",
            "category": "electrical",
            "skill_level": "beginner",
            "urgency": "low",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending_followup"
    assert body["next_followup"]["field"] == "power_isolated"


async def test_job_with_no_required_followups_can_assess_immediately(client):
    """Painting has no safety-critical follow-up fields in the placeholder
    mapping, so it should be assessable right after creation."""
    headers = await _auth_headers(client, "job2@example.com")
    create_resp = await client.post(
        "/jobs",
        json={
            "description": "paint the fence",
            "category": "painting",
            "skill_level": "beginner",
            "urgency": "low",
        },
        headers=headers,
    )
    job_id = create_resp.json()["id"]

    assess_resp = await client.post(f"/jobs/{job_id}/assess", headers=headers)
    assert assess_resp.status_code == 200
    body = assess_resp.json()
    assert body["status"] == "completed"
    assert 1 <= body["risk_level"] <= 5

    get_resp = await client.get(f"/assessments/{job_id}", headers=headers)
    assert get_resp.status_code == 200
    assessment = get_resp.json()
    assert assessment["status"] == "completed"
    assert assessment["job_id"] == job_id


async def test_electrical_job_requires_followup_before_assess(client):
    headers = await _auth_headers(client, "job3@example.com")
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
    job_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "pending_followup"

    # Assessing before follow-up is answered must be rejected, not silently
    # assessed as safe.
    assess_resp = await client.post(f"/jobs/{job_id}/assess", headers=headers)
    assert assess_resp.status_code == 409
    assert assess_resp.json()["error"]["code"] == "followup_incomplete"

    # Answer the safety-critical follow-up.
    followup_resp = await client.patch(
        f"/jobs/{job_id}/followup",
        json={"answers": {"power_isolated": True}},
        headers=headers,
    )
    assert followup_resp.status_code == 200
    assert followup_resp.json()["status"] == "ready_to_assess"

    assess_resp = await client.post(f"/jobs/{job_id}/assess", headers=headers)
    assert assess_resp.status_code == 200
    assert assess_resp.json()["status"] == "completed"


async def test_unanswered_followup_keeps_pending_and_never_defaults_safe(client):
    """A truly unresolved (never-answered) safety-critical field must NOT
    let the job advance to ready_to_assess (rules.md §4 point 4 / CLAUDE.md)."""
    headers = await _auth_headers(client, "job4@example.com")
    create_resp = await client.post(
        "/jobs",
        json={
            "description": "swap an outlet",
            "category": "electrical",
            "skill_level": "beginner",
            "urgency": "medium",
        },
        headers=headers,
    )
    job_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "pending_followup"

    # No answer submitted at all — must still block, forever, until answered.
    assess_resp = await client.post(f"/jobs/{job_id}/assess", headers=headers)
    assert assess_resp.status_code == 409


async def test_explicit_false_followup_answer_unblocks_and_escalates_risk(client):
    """An explicit `False` answer (the user honestly confirming the unsafe
    condition, e.g. "no, power is NOT isolated") is a *resolved* field, not
    a missing one — it must unblock assessment, and the rule engine's own
    escalation logic (ai/rule_engine/rules.py) must then push risk_level up
    for it. This is the srs.md exception-flow path: a job the user answers
    honestly-unsafe must still reach a real (Dangerous-tier) assessment,
    never get stuck 409ing forever just because the safe answer wasn't given."""
    headers = await _auth_headers(client, "job4b@example.com")
    create_resp = await client.post(
        "/jobs",
        json={
            "description": "swap an outlet",
            "category": "electrical",
            "skill_level": "beginner",
            "urgency": "medium",
        },
        headers=headers,
    )
    job_id = create_resp.json()["id"]

    followup_resp = await client.patch(
        f"/jobs/{job_id}/followup",
        json={"answers": {"power_isolated": False}},
        headers=headers,
    )
    assert followup_resp.status_code == 200
    assert followup_resp.json()["status"] == "ready_to_assess"
    assert followup_resp.json()["next_followup"] is None

    assess_resp = await client.post(f"/jobs/{job_id}/assess", headers=headers)
    assert assess_resp.status_code == 200
    assert assess_resp.json()["status"] == "completed"
    # An explicitly-unsafe answer escalates per catalog.FOLLOWUPS —
    # confirms the rule engine actually ran and escalated, not just that
    # assess "succeeded".
    assert assess_resp.json()["risk_level"] >= 4

    get_resp = await client.get(f"/assessments/{job_id}", headers=headers)
    triggered = get_resp.json()["triggered_rules"]
    # The distinction Phase 5 introduced: an answered-unsafe field is
    # `unsafe_followup:`, NOT `missing_followup:`. Conflating the two is the
    # bug that once made this whole path unreachable (memory.md 2026-07-19),
    # so assert both directions.
    assert "unsafe_followup:power_isolated" in triggered
    assert "missing_followup:power_isolated" not in triggered


async def test_job_ownership_enforced_404(client):
    headers_a = await _auth_headers(client, "owner_a@example.com")
    headers_b = await _auth_headers(client, "owner_b@example.com")

    create_resp = await client.post(
        "/jobs",
        json={
            "description": "paint a room",
            "category": "painting",
            "skill_level": "beginner",
            "urgency": "low",
        },
        headers=headers_a,
    )
    job_id = create_resp.json()["id"]

    # User B must not be able to see/act on user A's job — 404, not 403,
    # to avoid leaking existence.
    resp = await client.patch(f"/jobs/{job_id}/followup", json={"answers": {}}, headers=headers_b)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "job_not_found"


async def test_assessment_not_found_before_assess_404(client):
    headers = await _auth_headers(client, "job5@example.com")
    create_resp = await client.post(
        "/jobs",
        json={
            "description": "paint a room",
            "category": "painting",
            "skill_level": "beginner",
            "urgency": "low",
        },
        headers=headers,
    )
    job_id = create_resp.json()["id"]

    resp = await client.get(f"/assessments/{job_id}", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "assessment_not_found"
