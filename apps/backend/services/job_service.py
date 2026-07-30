"""Job orchestration: create_job, submit_followup, assess_job, list_jobs.

assess_job wires ai/classifier + ai/rule_engine together:
  final_risk = max(ml_risk, rule_risk)
and writes both a RiskAssessment and an AiLog row on every attempt,
including failures — an AI pipeline exception must never silently produce a
"safe" result (CLAUDE.md / rules.md §4).

`build_job_out` additionally computes `next_followup` (Gemini-phrased
wording for the first still-missing safety-critical field, or None) at
request time — it is never persisted on the Job model. The LLM call is
routed through ai/rule_engine/llm_assist, which has hardcoded fallbacks for
every case where Gemini is unavailable; nothing here blocks or errors the
job flow if that happens (rules.md §4).
"""

import asyncio
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.classifier import classify
from ai.rule_engine import evaluate, llm_assist
from ai.rule_engine.rules import required_followups
from core.errors import ApiError
from models import AiLog, Job, RiskAssessment
from schemas.job import FollowupPrompt, JobCreateRequest, JobFollowupRequest, JobOut

logger = logging.getLogger(__name__)

# Which follow-ups gate assessment is NOT defined here. It is derived from
# the hardcoded catalog via ai/rule_engine.required_followups(), so the set
# that blocks the workflow and the set the engine escalates on cannot drift
# apart. Phase 5 removed the duplicate table that used to live here: two
# copies of a safety-critical mapping is exactly the kind of thing that goes
# stale silently.
#
# It is also hazard-driven rather than category-driven now: chasing a wall
# before tiling needs `power_isolated` even though its category is `tiling`.


async def create_job(db: AsyncSession, user_id: UUID, payload: JobCreateRequest) -> Job:
    """Create a job, starting at "ready_to_assess" if its category has no
    required follow-ups, "pending_followup" otherwise — the same status
    transition `submit_followup` applies, so `status` is trustworthy
    immediately after creation instead of only becoming accurate after the
    first PATCH (a category with zero required fields, e.g. "general",
    would otherwise sit at "pending_followup" with `next_followup` already
    null — a real, observed inconsistency between the two signals).

    If `payload.category` is omitted, infer it via Gemini tagging
    (ai/rule_engine/llm_assist.tag_category) — that function already
    validates the result against the fixed TASK_CATEGORIES set and falls
    back to "general", so this call site can trust its return value as-is.
    The call is a blocking HTTP request, so it's run in a worker thread via
    asyncio.to_thread to avoid blocking the event loop.
    """
    category = payload.category
    if category is None:
        category = await asyncio.to_thread(llm_assist.tag_category, payload.description)

    job = Job(
        user_id=user_id,
        description=payload.description,
        category=category,
        skill_level=payload.skill_level,
        urgency=payload.urgency,
        followup_answers={},
        status="pending_followup",
    )
    job.status = "pending_followup" if _missing_required_followups(job) else "ready_to_assess"
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def get_owned_job(db: AsyncSession, job_id: UUID, user_id: UUID) -> Job:
    """Fetch a job, raising 404 if missing OR not owned by user_id (never
    leak existence of another user's job — same 404 either way)."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None or job.user_id != user_id:
        raise ApiError(404, "job_not_found", "No job found with that id.")
    return job


def _missing_required_followups(job: Job) -> set[str]:
    """Fields that still need an answer at all (key absent), not fields
    whose answer happens to be the unsafe one.

    "Missing" here means unresolved, per srs.md's exception flow: unresolved
    fields block assessment (this gate). An *answered* field — even an
    explicit `False`, i.e. the user confirming the unsafe condition — is
    resolved and must be allowed through to assess_job, where
    ai/rule_engine/rules.py's own falsy-answer check (a distinct, correct
    concern) is what escalates risk for it. Gating on truthiness here would
    make that escalation path unreachable: a job could never be assessed
    once a safety-critical answer was honestly "no," permanently 409ing
    instead of ever producing the Dangerous/Do-Not-Attempt result the rule
    engine is designed to compute for exactly that case.
    """
    required = required_followups(job.description, job.category, user_skill=job.skill_level)
    return {field for field in required if field not in job.followup_answers}


async def submit_followup(db: AsyncSession, job: Job, payload: JobFollowupRequest) -> Job:
    """Merge new follow-up answers into the job.

    Never silently advances past unanswered safety-critical fields: status
    only becomes "ready_to_assess" once every category-required field has
    been answered (any value, including an explicit `False` — see
    `_missing_required_followups`). Otherwise it stays "pending_followup".
    """
    merged = {**job.followup_answers, **payload.answers}
    job.followup_answers = merged

    if _missing_required_followups(job):
        job.status = "pending_followup"
    else:
        job.status = "ready_to_assess"

    await db.commit()
    await db.refresh(job)
    return job


async def list_jobs(db: AsyncSession, user_id: UUID) -> list[Job]:
    """The calling user's jobs, most recent first (frontend sidebar)."""
    result = await db.execute(
        select(Job).where(Job.user_id == user_id).order_by(Job.created_at.desc())
    )
    return list(result.scalars().all())


async def _next_followup_prompt(job: Job) -> FollowupPrompt | None:
    """The first still-missing required follow-up for `job`, with
    Gemini-phrased question wording, or None if nothing's missing.

    *Never* decides which fields are required (that's the hardcoded catalog
    via `required_followups()` / rules.md §4) — this only picks
    a deterministic field (sorted, so behavior is stable regardless of the
    underlying set's iteration order) among the already-known-missing ones
    and asks llm_assist for wording.
    """
    missing = _missing_required_followups(job)
    if not missing:
        return None
    field = sorted(missing)[0]
    question = await asyncio.to_thread(llm_assist.phrase_followup_question, field, job.category)
    return FollowupPrompt(field=field, question=question)


async def build_job_out(job: Job) -> JobOut:
    """Build the client-facing JobOut for `job`, including the computed
    (non-persisted) `next_followup`. Shared by every route that returns a
    job (create, submit_followup, list) so the attach-next_followup logic
    lives in one place."""
    job_out = JobOut.model_validate(job)
    job_out.next_followup = await _next_followup_prompt(job)
    return job_out


async def assess_job(db: AsyncSession, job: Job) -> RiskAssessment:
    """Run classifier + rule engine, compute final_risk = max(ml, rules),
    and persist a RiskAssessment + AiLog row.

    Raises ApiError(409) if follow-ups are incomplete (never assesses with
    known-missing safety-critical context). On any exception inside the AI
    pipeline itself, logs the failure to ai_logs, marks the job/assessment
    "failed", and returns the failed RiskAssessment rather than raising —
    callers can inspect `.status` to decide the HTTP response, but the
    system never silently returns a "safe" default.
    """
    if _missing_required_followups(job):
        raise ApiError(
            409,
            "followup_incomplete",
            "Safety-critical follow-up questions must be answered before assessment.",
        )

    model_input = {
        "description": job.description,
        "category": job.category,
        "skill_level": job.skill_level,
        "urgency": job.urgency,
        "followup_answers": job.followup_answers,
    }

    try:
        ml_risk, confidence = classify(job.description, job.category, job.skill_level)

        # LLM hazard tagging (rules.md §4.1): the LLM may only SELECT ids
        # from the hardcoded catalog, and every id is filtered against it
        # inside the engine. Returns [] on any failure, in which case the
        # deterministic keyword rules still run - the engine degrades to
        # "no LLM", never to "no hazards".
        llm_hazard_ids = await asyncio.to_thread(
            llm_assist.tag_hazards, job.description, job.category
        )

        rule_risk, triggered_rules = evaluate(
            job.description,
            job.category,
            job.followup_answers,
            llm_hazard_ids,
            user_skill=job.skill_level,
        )

        # THE non-negotiable invariant: rules only ever escalate.
        final_risk = max(ml_risk, rule_risk)
        if not (1 <= final_risk <= 5):
            raise ValueError(f"final_risk out of bounds: {final_risk}")

        explanation = _build_explanation(ml_risk, rule_risk, final_risk, triggered_rules)
        hazard_tags = list(triggered_rules)

        model_output = {
            "ml_risk": ml_risk,
            "ml_confidence": confidence,
            "rule_risk": rule_risk,
            "final_risk": final_risk,
        }

        assessment = RiskAssessment(
            job_id=job.id,
            risk_level=final_risk,
            confidence=confidence,
            explanation=explanation,
            hazard_tags=hazard_tags,
            triggered_rules=triggered_rules,
            status="completed",
        )
        job.status = "assessed"

    except Exception as exc:  # noqa: BLE001 - must fail loudly, never fall back to "safe"
        logger.exception("AI pipeline failure during assess_job for job_id=%s", job.id)
        model_output = {"error": str(exc), "error_type": type(exc).__name__}
        assessment = RiskAssessment(
            job_id=job.id,
            risk_level=5,  # worst plausible case placeholder; status="failed" blocks display
            confidence=0.0,
            explanation="Risk assessment failed. This task must not be treated as safe.",
            hazard_tags=[],
            triggered_rules=[],
            status="failed",
        )
        job.status = "failed"
        triggered_rules = []

    db.add(
        AiLog(
            job_id=job.id,
            model_input=model_input,
            model_output=model_output,
            triggered_rules=triggered_rules,
        )
    )
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)
    return assessment


def _build_explanation(
    ml_risk: int, rule_risk: int, final_risk: int, triggered_rules: list[str]
) -> str:
    """Templated explanation text — facts inserted, never freely generated
    (rules.md §4 point 3). No LLM call in this placeholder pipeline."""
    if not triggered_rules:
        return (
            f"Classifier predicted risk level {ml_risk}. No safety rules were "
            f"triggered. Final risk level: {final_risk}."
        )
    rule_list = ", ".join(triggered_rules)
    return (
        f"Classifier predicted risk level {ml_risk}. The following safety rules "
        f"were triggered: {rule_list} (rule engine risk level {rule_risk}). "
        f"Final risk level is the higher of the two: {final_risk}."
    )
