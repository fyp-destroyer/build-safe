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

from ai.rule_engine.llm_assist import CategoryTag, HazardTag, HazardTags, PhrasedQuestion
from models import Job
from schemas.job import TASK_CATEGORIES
from tests.conftest import register_and_login

pytestmark = pytest.mark.anyio


async def _auth_headers(client, email: str) -> dict:
    token = await register_and_login(client, email)
    return {"Authorization": f"Bearer {token}"}


def _description_from_prompt(prompt: str) -> str:
    """Pull the task description back out of the tagging prompt.

    Tags now have to quote the user's own words, and that quote is verified
    as a literal substring before the tag is accepted (llm_assist.
    `_evidence_supports`). A stub returning canned evidence would therefore
    have every tag discarded — so the stub quotes the description it was
    actually given, which is what a well-behaved model does.
    """
    marker = "Task description: "
    if marker not in prompt:
        return ""
    return prompt.split(marker, 1)[1].split("\n", 1)[0].strip()


def _make_llm_stub(*, category="carpentry", question=None, hazards=(), ask=()):
    """Build a generate_structured stub that dispatches on the requested
    schema, the way a real Gemini call does.

    A single request can now trigger all three call sites — category
    tagging, hazard tagging (moved to job creation so the follow-up gate and
    the rule engine see the same hazards) and question phrasing — so a stub
    that returns one canned object for every call would hand a
    `PhrasedQuestion` to the hazard parser.
    """
    default_question = question or "Have you confirmed this wall is not load-bearing?"

    def _stub(prompt: str, response_schema):
        if response_schema is CategoryTag:
            return CategoryTag(category=category)
        if response_schema is HazardTags:
            evidence = _description_from_prompt(prompt)
            return HazardTags(
                tags=[HazardTag(rule_id=h, evidence=evidence) for h in hazards],
                ask=list(ask),
            )
        return PhrasedQuestion(question=default_question)

    return _stub


_llm_stub = _make_llm_stub()


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

    stub = _make_llm_stub(
        category="electrical",
        question="Have you switched off the breaker for this circuit?",
    )
    with patch("ai.rule_engine.llm_assist.generate_structured", side_effect=stub):
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


async def test_llm_only_hazard_is_asked_about_before_it_can_escalate(client):
    """Regression (2026-07-31): a hazard the LLM tagger finds but keyword
    matching misses must produce a QUESTION at intake, not a silent level-5
    penalty at assessment.

    "replace my ceiling fans" matches none of `fixed_wiring_work`'s
    keywords. Hazard tagging used to run only inside assess_job, so the
    intake gate saw no hazards, asked nothing, and let the job through —
    then the tagger fired at assessment, made `power_isolated` required,
    found it unanswered, and applied its floor of 5. The user was told a
    safety-critical question went unanswered without ever being shown one.

    The fix is not "escalate less": it is that the tagged hazard set is
    resolved once at creation and persisted, so the set that decides what is
    ASKED is the same set that decides how the job is SCORED.
    """
    headers = await _auth_headers(client, "llm_hazard_gate@example.com")
    stub = _make_llm_stub(
        category="electrical",
        question="Have you confirmed the power to this circuit is isolated?",
        hazards=["fixed_wiring_work"],
    )

    with patch("ai.rule_engine.llm_assist.generate_structured", side_effect=stub):
        create_resp = await client.post(
            "/jobs",
            json={
                "description": "i want to replace my ceiling fans",
                "skill_level": "beginner",
            },
            headers=headers,
        )
        assert create_resp.status_code == 201
        body = create_resp.json()

        # The whole point: the question is surfaced up front.
        assert body["status"] == "pending_followup"
        assert body["next_followup"] is not None
        assert body["next_followup"]["field"] == "power_isolated"

        job_id = body["id"]

        # And assessment is blocked until it's answered — never assessed
        # while a field the engine will escalate on is still unanswered.
        assert (await client.post(f"/jobs/{job_id}/assess", headers=headers)).status_code == 409

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

    get_resp = await client.get(f"/assessments/{job_id}", headers=headers)
    triggered = get_resp.json()["triggered_rules"]
    # The LLM-tagged hazard still fires and still escalates — this is not a
    # de-escalation. What must not survive is the missing-answer penalty for
    # a question the user was never asked.
    assert "fixed_wiring_work" in triggered
    assert "missing_followup:power_isolated" not in triggered


async def test_hazard_tagging_failure_at_creation_never_escalates_on_unasked_field(client):
    """If Gemini is down at creation, the job is stored untagged (NULL, not
    []) and re-tagged on the next request. A hazard discovered by that retry
    must send the user back to answer its follow-up (409), never be scored
    against them as "unanswered"."""
    headers = await _auth_headers(client, "llm_hazard_retry@example.com")

    # Creation: every LLM call fails -> untagged, keyword-only.
    with patch("ai.rule_engine.llm_assist.generate_structured", return_value=None):
        create_resp = await client.post(
            "/jobs",
            json={
                "description": "i want to replace my ceiling fans",
                "category": "electrical",
                "skill_level": "beginner",
            },
            headers=headers,
        )
        assert create_resp.status_code == 201
        body = create_resp.json()
        job_id = body["id"]
        # No keyword match and no tagger -> nothing known to ask about yet.
        assert body["next_followup"] is None

    # Assessment: tagging succeeds this time and surfaces the hazard. The
    # follow-up it requires is unanswered, so assessment must refuse rather
    # than apply the missing-answer floor.
    stub = _make_llm_stub(
        category="electrical",
        question="Have you confirmed the power to this circuit is isolated?",
        hazards=["fixed_wiring_work"],
    )
    with patch("ai.rule_engine.llm_assist.generate_structured", side_effect=stub):
        assess_resp = await client.post(f"/jobs/{job_id}/assess", headers=headers)
        assert assess_resp.status_code == 409
        assert assess_resp.json()["error"]["code"] == "followup_incomplete"

        # ...and the question is now available to ask (what the chat UI's
        # followup_incomplete recovery path re-reads).
        refreshed = await client.patch(
            f"/jobs/{job_id}/followup", json={"answers": {}}, headers=headers
        )
        assert refreshed.json()["next_followup"]["field"] == "power_isolated"


async def test_ambiguous_height_becomes_a_question_not_an_assumed_hazard(client):
    """End-to-end regression for the bulb case (observed live, 2026-08-01).

    "how do i change my light bulb", beginner, power off -> level 3, because
    the tagger inferred `work_at_height` from a ceiling nobody mentioned and
    `fixed_wiring_work` from a bulb that is a consumable, not an installation.
    Neither rule keyword-matches; both were the model filling in facts.

    The intended behaviour, and what this asserts: an unstated height becomes
    a QUESTION. The user answers it, the gate closes, and a bulb swap comes
    back as safe DIY.
    """
    headers = await _auth_headers(client, "bulb_height@example.com")
    # A well-behaved tagger: it cannot quote any height, so instead of
    # guessing `work_at_height` it tags the gated rule and asks.
    stub = _make_llm_stub(
        category="electrical",
        question="Can you reach it from floor level or a step ladder?",
        hazards=["overhead_work_unknown_height"],
        ask=["height_access"],
    )

    with patch("ai.rule_engine.llm_assist.generate_structured", side_effect=stub):
        create_resp = await client.post(
            "/jobs",
            json={"description": "how do i change my light bulb", "skill_level": "beginner"},
            headers=headers,
        )
        assert create_resp.status_code == 201
        body = create_resp.json()
        job_id = body["id"]

        # Asked, not assumed.
        assert body["status"] == "pending_followup"
        assert body["next_followup"]["field"] == "height_access"

        # Unanswered, the hazard stands: assessment is blocked, never
        # silently resolved in the user's favour.
        assert (await client.post(f"/jobs/{job_id}/assess", headers=headers)).status_code == 409

        answered = await client.patch(
            f"/jobs/{job_id}/followup",
            json={"answers": {"height_access": True}},
            headers=headers,
        )
        assert answered.status_code == 200
        assert answered.json()["status"] == "ready_to_assess"

        assess_resp = await client.post(f"/jobs/{job_id}/assess", headers=headers)

    assert assess_resp.status_code == 200
    result = assess_resp.json()
    assert result["status"] == "completed"

    get_resp = await client.get(f"/assessments/{job_id}", headers=headers)
    assessment = get_resp.json()
    triggered = assessment["triggered_rules"]

    assert "work_at_height" not in triggered, "height was never stated and must not be assumed"
    assert "fixed_wiring_work" not in triggered, "a bulb is a consumable, not fixed wiring"
    assert "overhead_work_unknown_height" not in triggered, "the user closed this gate"
    assert assessment["risk_level"] == 1, f"a bulb swap should be safe DIY, got {assessment}"


async def test_denied_height_access_keeps_the_hazard_in_force(client):
    """The other half of the gate: answering "no, I need roof access" must
    keep the hazard firing. A gate is a refinement, not an escape hatch."""
    headers = await _auth_headers(client, "bulb_height_denied@example.com")
    stub = _make_llm_stub(
        category="electrical",
        question="Can you reach it from floor level or a step ladder?",
        hazards=["overhead_work_unknown_height"],
        ask=["height_access"],
    )

    with patch("ai.rule_engine.llm_assist.generate_structured", side_effect=stub):
        create_resp = await client.post(
            "/jobs",
            json={
                "description": "change the bulb in the stairwell light",
                "skill_level": "beginner",
            },
            headers=headers,
        )
        job_id = create_resp.json()["id"]

        await client.patch(
            f"/jobs/{job_id}/followup",
            json={"answers": {"height_access": False}},
            headers=headers,
        )
        assess_resp = await client.post(f"/jobs/{job_id}/assess", headers=headers)

    assert assess_resp.status_code == 200
    get_resp = await client.get(f"/assessments/{job_id}", headers=headers)
    assessment = get_resp.json()
    assert "overhead_work_unknown_height" in assessment["triggered_rules"]
    assert assessment["risk_level"] >= 3
