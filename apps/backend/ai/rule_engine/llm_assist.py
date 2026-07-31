"""LLM-assisted category tagging + follow-up question phrasing.

**What this module is allowed to do, and nothing more** (rules.md §4 /
CLAUDE.md): (a) pick a category string from the fixed, closed 9-value
`TASK_CATEGORIES` set for a free-text task description ("tagging"), (b) tag
which *existing* catalog hazard rule ids apply to a description, and (c)
phrase the natural-language wording of a question about an
*already-hardcoded* follow-up field.

It cannot invent a rule, cannot assign or suggest a risk number, and cannot
change any escalation floor: every id it proposes is filtered against
`catalog.VALID_RULE_IDS` inside `ai/rule_engine/rules.py` before it can
influence anything, and the floors themselves are hardcoded in
`catalog.py`. Tagging is additive only — it can cause a hardcoded rule to
fire that keyword matching missed, never suppress one that matched.

Because which follow-ups are required is derived from which hazard rules
fired (`rules.required_followups`), tagging does indirectly widen the set of
questions asked. That is intended, but it means the tagged set must be
*identical* everywhere it is consulted — `services/job_service.py` resolves
it once per job and persists it for exactly that reason.

Every call into Gemini goes through `ai.llm.client.generate_structured`,
which never raises and returns `None` on any failure — every function here
has a hardcoded, safe fallback for that case and never blocks or errors the
job flow just because Gemini is unavailable.
"""

import logging

from pydantic import BaseModel

from ai.llm.client import generate_structured
from schemas.job import TASK_CATEGORIES

logger = logging.getLogger(__name__)

_FALLBACK_CATEGORY = "general"

# Hardcoded default phrasings, keyed by the same field names hardcoded in
# ai/rule_engine/rules.py's _SAFETY_CRITICAL_FOLLOWUPS and
# services/job_service.py's _REQUIRED_FOLLOWUPS_BY_CATEGORY. Used whenever
# Gemini is unavailable or returns an empty/whitespace answer — the flow
# must never block just because the LLM is down.
_DEFAULT_FOLLOWUP_QUESTIONS: dict[str, str] = {
    "power_isolated": (
        "Have you confirmed the power to this circuit is fully isolated at "
        "the breaker before starting?"
    ),
    "load_bearing_confirmed": (
        "Have you confirmed the wall or structure involved is NOT load-bearing?"
    ),
    "gas_line_present": "Have you confirmed there is no gas line present near this work area?",
}


class CategoryTag(BaseModel):
    """Structured-output schema for Gemini's category tagging call."""

    category: str


class PhrasedQuestion(BaseModel):
    """Structured-output schema for Gemini's follow-up phrasing call."""

    question: str


def tag_category(description: str) -> str:
    """Classify a free-text task description into one of the fixed 9
    `TASK_CATEGORIES`.

    Defense in depth: even though `generate_structured` constrains the JSON
    *shape*, the returned `category` string is still explicitly checked
    against `TASK_CATEGORIES` (case-insensitive) before being trusted — an
    LLM-invented category string must never reach the database. Falls back
    to "general" if Gemini is unavailable or returns anything outside the
    fixed set.
    """
    prompt = (
        "Classify the following DIY/construction task description into "
        "exactly one of these fixed categories: "
        f"{', '.join(TASK_CATEGORIES)}.\n"
        "Respond with only the single best-matching category string from "
        "that exact list — never invent a category outside this list.\n\n"
        f"Task description: {description!r}"
    )

    result = generate_structured(prompt, CategoryTag)
    if result is None:
        logger.warning("Gemini category tagging unavailable; falling back to 'general'.")
        return _FALLBACK_CATEGORY

    normalized = result.category.strip().lower()
    if normalized not in TASK_CATEGORIES:
        logger.warning(
            "Gemini returned a category outside the fixed set (%r); falling back to 'general'.",
            result.category,
        )
        return _FALLBACK_CATEGORY

    return normalized


def phrase_followup_question(field: str, category: str) -> str:
    """Phrase a natural, user-facing yes/no-style question about an
    already-hardcoded safety-critical follow-up field.

    This function has zero say over *whether* `field` is required or how a
    missing answer affects risk — it only supplies wording. Falls back to a
    hardcoded default phrasing (`_DEFAULT_FOLLOWUP_QUESTIONS`) if Gemini is
    unavailable or returns an empty/whitespace question.
    """
    fallback = _DEFAULT_FOLLOWUP_QUESTIONS.get(field, f"Please confirm: {field.replace('_', ' ')}?")

    prompt = (
        "Phrase a single, natural, user-facing yes/no-style safety question "
        f"for a home DIY/construction app. The task category is {category!r} "
        f"and the underlying safety field being confirmed is {field!r}. "
        "Keep it short, plain-language, and specific to that field. Do not "
        "state any safety fact yourself — only ask the question."
    )

    result = generate_structured(prompt, PhrasedQuestion)
    if result is None or not result.question.strip():
        logger.warning(
            "Gemini follow-up phrasing unavailable for field=%r; using hardcoded default.",
            field,
        )
        return fallback

    return result.question.strip()


# ---------------------------------------------------------------------------
# Phase 5: LLM hazard tagging.
#
# The LLM's entire authority here is to SELECT ids from the hardcoded catalog.
# It cannot invent a hazard, cannot assign or suggest a risk number, and
# cannot change a floor - those live in ai/rule_engine/catalog.py and change
# only by code review (rules.md §4.1).
#
# Everything it returns is filtered against catalog.VALID_RULE_IDS, so a
# hallucinated id is discarded rather than trusted. Failure is safe by
# construction: on any error this returns [] and the deterministic keyword
# rules still run, so the engine degrades to "no LLM" rather than to "no
# hazards".
# ---------------------------------------------------------------------------
class HazardTags(BaseModel):
    """Structured-output schema for Gemini's hazard tagging call."""

    rule_ids: list[str] = []


def tag_hazards(description: str, category: str) -> list[str]:
    """Ask the LLM which hardcoded catalog rules apply. Never trusts the reply.

    Returns only ids that exist in the catalog. Returns [] if Gemini is
    unavailable, returns nothing usable, or returns only invalid ids - the
    caller's keyword matching is unaffected either way.

    Callers that need to tell "Gemini was down" apart from "Gemini ran and
    found no hazards" must use `tag_hazards_result` instead: the two cases
    are indistinguishable here and conflating them would let a job cache an
    empty hazard set produced by an outage.
    """
    return tag_hazards_result(description, category) or []


def tag_hazards_result(description: str, category: str) -> list[str] | None:
    """`tag_hazards`, but returns None when the LLM produced no usable reply.

    None means "not tagged" (retry later); [] means "tagged, no hazards
    apply". `services/job_service.py` persists the distinction so a job
    tagged during a Gemini outage is re-tagged rather than permanently
    treated as hazard-free.
    """
    from ai.rule_engine.catalog import RULES, VALID_RULE_IDS

    # The menu carries each rule's full explanation and example wording, not
    # just its one-line summary. Summaries alone are too terse to scope a
    # rule: "Exposed conductors of unverified status" reads as applicable to
    # any job that briefly exposes a wire, so a routine light-fitting swap got
    # tagged with a rule meant for an ACTIVE fault (its keywords are "live
    # wire", "sparking", "arcing", "burning smell") — and that rule has a
    # floor of 5, so every light fitting came back Do-Not-Attempt. Observed
    # live, 2026-07-31. Showing the explanation and the example phrases is
    # what lets the model tell "hazard present" from "hazard conceivable".
    menu = "\n".join(
        f'- id: "{r.id}"\n'
        f"    {r.summary}\n"
        f"    applies when: {r.explanation}\n"
        f"    typical wording: {', '.join(r.keywords[:6])}"
        for r in RULES.values()
    )
    prompt = (
        "You are tagging which known hazards apply to a home improvement task.\n"
        "Choose ONLY from this fixed list of hazard ids. Do not invent ids, do "
        "not rate severity, and do not assign any risk level.\n\n"
        "TAG every hazard that is inherent to the work being described. "
        "Replacing a light fitting, a ceiling fan or a socket IS work on "
        "fixed wiring, so tag it even if the description never uses the word "
        "'wiring'. This is the main thing you are here for: catching hazards "
        "that are obvious from the work itself.\n\n"
        "DO NOT tag a hazard that describes a different location or a fault "
        "the description does not report. Work on a fitting is not work on "
        "the incoming supply or consumer unit. Wiring that is simply "
        "disconnected during routine work is not a reported live-conductor "
        "fault — that hazard is for sparking, arcing or a wire found live, "
        "which the user would have said.\n\n"
        f"Task category: {category}\n"
        f"Task description: {description}\n\n"
        "Return the ids that apply, copied EXACTLY as written above, "
        'character for character — "fixed_wiring_work", not "fixed_wiring"; '
        '"work_at_height", not "working_at_height". An id that is not an '
        "exact match is discarded, so an approximate answer is the same as no "
        "answer. Return an empty list if none apply.\n\n"
        f"Valid ids: {', '.join(sorted(VALID_RULE_IDS))}"
    )

    result = generate_structured(prompt, HazardTags)
    if result is None:
        logger.info("tag_hazards: no LLM result, falling back to keyword rules only")
        return None

    valid, invalid = [], []
    for rid in result.rule_ids or []:
        (valid if rid in VALID_RULE_IDS else invalid).append(rid)
    if invalid:
        # A model returning ids outside the catalog is a model error, never a
        # new rule. Logged loudly because silent discards hide prompt drift.
        logger.warning(
            "tag_hazards: discarded %d id(s) outside the hardcoded " "catalog: %s",
            len(invalid),
            invalid,
        )
    return list(dict.fromkeys(valid))
