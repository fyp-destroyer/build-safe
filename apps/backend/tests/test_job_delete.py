"""DELETE /jobs/{id} — removing a conversation from the sidebar.

Three things matter: it actually removes the job (not just hides it), it
takes the job's children with it (transcript, assessment, ai_logs — every
one of those tables has a NOT NULL FK back to jobs, so a partial delete is a
500, and a *skipped* delete would leave the user's task text behind after
they asked for it to be gone), and it is ownership-scoped like every other
job route.
"""

import pytest
from sqlalchemy import select

from models import AiLog, ChatMessage, Job, RiskAssessment
from tests.conftest import register_and_login

pytestmark = pytest.mark.anyio


async def _auth_headers(client, email: str) -> dict:
    token = await register_and_login(client, email)
    return {"Authorization": f"Bearer {token}"}


async def _make_job(client, headers, description="paint the hallway") -> str:
    resp = await client.post(
        "/jobs",
        json={"description": description, "category": "painting", "skill_level": "beginner"},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_delete_removes_job_from_listing(client):
    headers = await _auth_headers(client, "del1@example.com")
    job_id = await _make_job(client, headers)

    resp = await client.delete(f"/jobs/{job_id}", headers=headers)
    assert resp.status_code == 204

    listed = (await client.get("/jobs", headers=headers)).json()
    assert [job["id"] for job in listed] == []
    # Gone, not merely unlisted.
    assert (await client.get(f"/jobs/{job_id}/messages", headers=headers)).status_code == 404


async def test_delete_takes_transcript_and_assessment_with_it(client, db_session):
    headers = await _auth_headers(client, "del2@example.com")
    job_id = await _make_job(client, headers)
    await client.post(
        f"/jobs/{job_id}/messages",
        json={"messages": [{"role": "user", "text": "paint the hallway"}]},
        headers=headers,
    )
    assert (await client.post(f"/jobs/{job_id}/assess", headers=headers)).status_code == 200

    assert (await client.delete(f"/jobs/{job_id}", headers=headers)).status_code == 204

    for model in (Job, ChatMessage, RiskAssessment, AiLog):
        column = model.id if model is Job else model.job_id
        rows = (await db_session.execute(select(model).where(column == job_id))).scalars().all()
        assert rows == [], f"{model.__name__} rows survived the job delete"


async def test_delete_is_scoped_to_the_owner(client):
    """Someone else's job 404s and stays intact — never leak existence."""
    headers_a = await _auth_headers(client, "del_owner@example.com")
    headers_b = await _auth_headers(client, "del_intruder@example.com")
    job_id = await _make_job(client, headers_a)

    assert (await client.delete(f"/jobs/{job_id}", headers=headers_b)).status_code == 404

    listed = (await client.get("/jobs", headers=headers_a)).json()
    assert [job["id"] for job in listed] == [job_id]


async def test_delete_requires_authentication(client):
    headers = await _auth_headers(client, "del3@example.com")
    job_id = await _make_job(client, headers)

    assert (await client.delete(f"/jobs/{job_id}")).status_code == 401
