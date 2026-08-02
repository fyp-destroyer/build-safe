"""Job orchestration: create_job, submit_followup, assess_job, list_jobs.

assess_job wires ai/classifier + ai/rule_engine together:
  final_risk = max(ml_risk, rule_risk)
and writes both a RiskAssessment and an AiLog row on every attempt,
including failures — an AI pipeline exception must never silently produce a
"safe" result (CLAUDE.md / rules.md §4).

RULES-ONLY MODE (`RISK_USE_ML_CLASSIFIER=false`, off in dev since
2026-08-01): the classifier still runs and its prediction is still written to
`ai_logs`, but it is excluded from the max() and `final_risk = rule_risk`.
Because a max() can only shrink when a term is removed, this is strictly a
reduction in escalation: a task matching no keyword and receiving no LLM
hazard tag now returns level 1 unopposed. See `core/config.py` for why that
was judged acceptable (the classifier is currently a near-constant function
of `user_skill`) and what would restore the documented pipeline.

LLM hazard tags are resolved ONCE, at job creation, and persisted on
`jobs.llm_hazard_ids`. Everything downstream — the follow-up gate, the
question shown to the user, and the rule engine at assessment — reads that
one column, so the hazard set that decides what the user is ASKED can never
differ from the one that decides how the task is SCORED. See `_hazard_ids`
for the bug that made this necessary.

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

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.classifier import classify
from ai.rule_engine import evaluate, llm_assist
from ai.rule_engine.rules import required_followups
from core.config import get_settings
from core.errors import ApiError
from models import AiLog, ChatMessage, Job, RiskAssessment
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

    # Resolve LLM hazard tags HERE, once, and persist them — see
    # `_hazard_ids` for why this must not be re-derived per step.
    tagged = await asyncio.to_thread(llm_assist.tag_hazards_result, payload.description, category)

    job = Job(
        user_id=user_id,
        description=payload.description,
        category=category,
        skill_level=payload.skill_level,
        urgency=payload.urgency,  # optional; nothing consumes it (srs.md FR-02)
        followup_answers={},
        llm_hazard_ids=None if tagged is None else tagged.rule_ids,
        llm_followup_fields=None if tagged is None else tagged.ask_fields,
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


def _hazard_ids(job: Job) -> list[str]:
    """The LLM-proposed catalog rule ids resolved for this job, or [].

    Read from the persisted column, never re-derived. The follow-up gate
    (`_missing_required_followups`), the question shown to the user
    (`_next_followup_prompt`) and the escalation (`assess_job`) all read
    this one value, so they cannot disagree about which hazards apply.

    They used to disagree: tagging ran only inside `assess_job`, while the
    gate matched keywords alone. "replace my ceiling fans" matches no
    keyword, so no follow-up was required and none was asked — then the
    tagger flagged `fixed_wiring_work` at assessment, which made
    `power_isolated` required, unanswered, and worth a level-5 floor. The
    user was told a safety-critical question went unanswered without ever
    having been shown one. Rules may only escalate on facts the user had a
    chance to supply.

    A NULL column means tagging never succeeded (Gemini was down at
    creation); the job degrades to keyword-only hazards, which is the
    documented no-LLM behaviour, and `ensure_hazard_ids` retries later.
    """
    return job.llm_hazard_ids or []


def _asked_fields(job: Job) -> list[str]:
    """Follow-up fields the tagger asked for, or [].

    Read from the persisted column for the same reason as `_hazard_ids`: the
    questions the user is shown and the fields assessment scores against must
    be one set, not two derivations that can disagree. Unioned with the
    catalog-derived fields inside `required_followups`, never subtracted —
    the LLM widens the question set and can never narrow it.
    """
    return job.llm_followup_fields or []


async def ensure_hazard_ids(db: AsyncSession, job: Job) -> Job:
    """Tag and persist hazard ids for a job that has none yet (NULL).

    Covers jobs created before this column existed and jobs whose creation
    happened during an LLM outage. Re-tagging can only ADD hazards and
    questions, so it can only widen the required follow-up set — never
    narrow it. Callers must therefore run this BEFORE the follow-up gate, so
    any newly discovered question is asked rather than silently penalised.
    """
    if job.llm_hazard_ids is not None:
        return job
    tagged = await asyncio.to_thread(llm_assist.tag_hazards_result, job.description, job.category)
    if tagged is None:
        return job  # still unavailable; stay NULL and retry on the next pass
    job.llm_hazard_ids = tagged.rule_ids
    job.llm_followup_fields = tagged.ask_fields
    if job.status in ("pending_followup", "ready_to_assess"):
        job.status = "pending_followup" if _missing_required_followups(job) else "ready_to_assess"
    await db.commit()
    await db.refresh(job)
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
    required = required_followups(
        job.description,
        job.category,
        _hazard_ids(job),
        user_skill=job.skill_level,
        followup_answers=job.followup_answers,
        llm_asked_fields=_asked_fields(job),
    )
    return {field for field in required if field not in job.followup_answers}


async def submit_followup(db: AsyncSession, job: Job, payload: JobFollowupRequest) -> Job:
    """Merge new follow-up answers into the job.

    Never silently advances past unanswered safety-critical fields: status
    only becomes "ready_to_assess" once every category-required field has
    been answered (any value, including an explicit `False` — see
    `_missing_required_followups`). Otherwise it stays "pending_followup".
    """
    # Retry tagging first if creation-time tagging failed, so a hazard we
    # only learn about now still turns into a question instead of an
    # unanswerable penalty at assessment.
    job = await ensure_hazard_ids(db, job)

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


async def delete_job(db: AsyncSession, job: Job) -> None:
    """Delete a job and everything that hangs off it, in FK order.

    Child rows are removed explicitly rather than via ORM cascades: none of
    the relationships declare one, and every child table's `job_id` is NOT
    NULL, so a bare job delete would just raise a FK violation.

    The `ai_logs` rows go too. rules.md §4 point 6 requires that every
    assessment attempt IS logged (no sampling) — it does not require the log
    to outlive the user's own task, and those rows embed the task
    description, so keeping them after the user deletes the conversation
    would leave the user data behind precisely where they asked for it to be
    gone.
    """
    await db.execute(delete(ChatMessage).where(ChatMessage.job_id == job.id))
    await db.execute(delete(RiskAssessment).where(RiskAssessment.job_id == job.id))
    await db.execute(delete(AiLog).where(AiLog.job_id == job.id))
    await db.delete(job)
    await db.commit()


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
    # Last chance to tag if creation-time tagging failed. Must run BEFORE the
    # gate: a hazard discovered here may add a follow-up, and the correct
    # response to that is to send the user back to answer it (409), never to
    # assess and escalate on the unanswered field.
    job = await ensure_hazard_ids(db, job)

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

    use_ml = get_settings().RISK_USE_ML_CLASSIFIER

    try:
        # The classifier runs either way, so its prediction is always on
        # record in ai_logs and a broken model is always visible. Only its
        # CONTRIBUTION to the decision is gated (see RISK_USE_ML_CLASSIFIER).
        ml_risk: int | None = None
        confidence = 0.0
        ml_error: str | None = None
        try:
            ml_risk, confidence = classify(job.description, job.category)
        except Exception as exc:  # noqa: BLE001 - re-raised below when it matters
            if use_ml:
                # The documented pipeline depends on this number; failing to
                # get it must fail the assessment, never default to "safe".
                raise
            # Rules-only mode: the classifier has no say, so its failure
            # cannot make the result wrong. Recorded rather than swallowed.
            logger.warning("classifier unavailable (rules-only mode active): %s", exc)
            ml_error = f"{type(exc).__name__}: {exc}"

        # LLM hazard tagging (rules.md §4.1): the LLM may only SELECT ids
        # from the hardcoded catalog, and every id is filtered against it
        # inside the engine. Read from the job rather than re-tagged here:
        # the gate above must have been evaluated against the SAME ids, or
        # assessment can escalate on a hazard whose follow-up was never
        # asked (see `_hazard_ids`). Empty means keyword rules alone still
        # run - the engine degrades to "no LLM", never to "no hazards".
        llm_hazard_ids = _hazard_ids(job)

        rule_risk, triggered_rules = evaluate(
            job.description,
            job.category,
            job.followup_answers,
            llm_hazard_ids,
            user_skill=job.skill_level,
            llm_asked_fields=_asked_fields(job),
        )

        # THE non-negotiable invariant: rules only ever escalate.
        #
        # With the classifier enabled this is the documented
        # `final_risk = max(ml_risk, rule_risk)`. With it disabled the rule
        # floor stands alone — strictly lower or equal, never higher, which
        # is exactly the coverage cost documented on RISK_USE_ML_CLASSIFIER.
        final_risk = max(ml_risk, rule_risk) if (use_ml and ml_risk is not None) else rule_risk
        if not (1 <= final_risk <= 5):
            raise ValueError(f"final_risk out of bounds: {final_risk}")

        explanation = _build_explanation(
            ml_risk, rule_risk, final_risk, triggered_rules, use_ml=use_ml
        )
        hazard_tags = list(triggered_rules)

        model_output = {
            "ml_risk": ml_risk,
            "ml_confidence": confidence,
            "rule_risk": rule_risk,
            "final_risk": final_risk,
            # Explicit, not inferred: a future reader of ai_logs must be able
            # to tell "the classifier agreed" from "the classifier was not
            # consulted", which ml_risk alone cannot express.
            "ml_used": use_ml,
        }
        if ml_error:
            model_output["ml_error"] = ml_error

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
    ml_risk: int | None,
    rule_risk: int,
    final_risk: int,
    triggered_rules: list[str],
    *,
    use_ml: bool = True,
) -> str:
    """Templated explanation text — facts inserted, never freely generated
    (rules.md §4 point 3). No LLM call in this placeholder pipeline.

    The text must describe the pipeline that actually ran. When the
    classifier is not contributing (RISK_USE_ML_CLASSIFIER=false) it must not
    be cited as a reason — telling a user "Classifier predicted 4" for a
    number the classifier had no part in is a false explanation of a safety
    decision, which is worse than a terse one.
    """
    rule_list = ", ".join(triggered_rules)

    if not use_ml or ml_risk is None:
        if not triggered_rules:
            return (
                f"No safety rules were triggered for this task. Final risk " f"level: {final_risk}."
            )
        return (
            f"The following safety rules were triggered: {rule_list}. "
            f"Final risk level: {final_risk}."
        )

    if not triggered_rules:
        return (
            f"Classifier predicted risk level {ml_risk}. No safety rules were "
            f"triggered. Final risk level: {final_risk}."
        )
    return (
        f"Classifier predicted risk level {ml_risk}. The following safety rules "
        f"were triggered: {rule_list} (rule engine risk level {rule_risk}). "
        f"Final risk level is the higher of the two: {final_risk}."
    )
