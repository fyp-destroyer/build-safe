"""LLM-assisted category tagging + follow-up question phrasing.

**What this module is allowed to do, and nothing more** (rules.md §4 /
CLAUDE.md): (a) pick a category string from the fixed, closed 9-value
`TASK_CATEGORIES` set for a free-text task description ("tagging"), (b) tag
which *existing* catalog hazard rule ids apply to a description, (c) select
which *existing* follow-up fields to ask about when the description is
ambiguous, and (d) phrase the natural-language wording of a question about
an *already-hardcoded* follow-up field.

It cannot invent a rule or a question, cannot assign or suggest a risk
number, and cannot change any escalation floor: every id it proposes is
filtered against `catalog.VALID_RULE_IDS` (or
`LLM_SELECTABLE_FOLLOWUP_FIELDS`) before it can influence anything, and the
floors themselves are hardcoded in `catalog.py`. Every contribution is
additive only — it can cause a hardcoded rule to fire that keyword matching
missed, or a hardcoded question to be asked that the catalog did not derive,
never suppress either.

EVIDENCE GROUNDING (2026-08-01)
-------------------------------
Every proposed hazard must quote the user's own words that justify it, and
that quote is verified as a literal substring of the description before the
tag is accepted. A model cannot quote text the user never wrote, so a hazard
it merely inferred is discarded mechanically rather than argued out of it in
the prompt.

This exists because prose alone did not hold. The previous prompt already
said "do not tag a hazard the description does not report" and still
returned `work_at_height` for "how do I change my light bulb" — the model
reasoned bulb -> ceiling -> overhead -> height and tagged a level-3 hazard
the user had said nothing about. Where a hazard depends on a fact the user
has not stated, the model now puts the matching follow-up field in `ask`
instead of guessing: uncertainty becomes a question, not a tag.

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
    "height_access": (
        "Can you reach this comfortably from floor level or a step ladder, "
        "without needing roof or upper-storey access?"
    ),
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
class HazardTag(BaseModel):
    """One proposed hazard, with the user's own words that justify it.

    `evidence` must be a verbatim span from the task description. It is
    verified as a substring before the tag is accepted - see
    `_evidence_supports`. This is what stops the model from tagging a hazard
    it merely imagined: it cannot quote text the user never wrote.
    """

    rule_id: str
    evidence: str


class HazardTags(BaseModel):
    """Structured-output schema for the hazard tagging call.

    `ask` lets the model route an AMBIGUITY into a question instead of
    resolving it by guessing a tag. Fields are validated against the closed
    `LLM_SELECTABLE_FOLLOWUP_FIELDS` set and are additive only - see
    `rules.required_followups`.
    """

    tags: list[HazardTag] = []
    ask: list[str] = []


class TagResult(BaseModel):
    """What the tagger resolved for a job: hazards, plus questions to ask."""

    rule_ids: list[str] = []
    ask_fields: list[str] = []


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace, for substring evidence checking."""
    return " ".join((text or "").lower().split())


def _evidence_supports(description: str, evidence: str) -> bool:
    """Is `evidence` actually a span of what the user wrote?

    The check is deliberately mechanical rather than semantic. A prompt
    instruction not to assume is weak - the previous prompt already said "DO
    NOT tag a hazard the description does not report" and still produced
    `work_at_height` for "how do I change my light bulb", because the model
    inferred bulb -> ceiling -> overhead -> height. Requiring a quote the
    model cannot produce is what actually closes that path.

    Whitespace and case are normalised so trivial reformatting does not
    reject an otherwise-honest quote; nothing else is relaxed.
    """
    ev = _normalize(evidence)
    if not ev:
        return False
    return ev in _normalize(description)


def tag_hazards(description: str, category: str) -> list[str]:
    """Ask the LLM which hardcoded catalog rules apply. Never trusts the reply.

    Returns only ids that exist in the catalog and whose evidence checks out.
    Returns [] if the LLM is unavailable, returns nothing usable, or returns
    only invalid ids - the caller's keyword matching is unaffected either way.

    Callers that need to tell "the LLM was down" apart from "it ran and found
    no hazards" must use `tag_hazards_result` instead: the two cases are
    indistinguishable here and conflating them would let a job cache an empty
    hazard set produced by an outage.
    """
    result = tag_hazards_result(description, category)
    return [] if result is None else list(result.rule_ids)


def tag_hazards_result(description: str, category: str) -> TagResult | None:
    """`tag_hazards`, but returns None when the LLM produced no usable reply,
    and carries the follow-up fields it wants asked.

    None means "not tagged" (retry later); a TagResult with empty `rule_ids`
    means "tagged, no hazards apply". `services/job_service.py` persists the
    distinction so a job tagged during an outage is re-tagged rather than
    permanently treated as hazard-free.
    """
    from ai.rule_engine.catalog import (
        FOLLOWUPS_BY_FIELD,
        LLM_SELECTABLE_FOLLOWUP_FIELDS,
        RULES,
        VALID_RULE_IDS,
    )

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
        f"    typical wording: {', '.join(r.keywords[:6]) or '(no typical wording)'}"
        for r in RULES.values()
    )
    question_menu = "\n".join(
        f'- field: "{FOLLOWUPS_BY_FIELD[f].field}"\n    asks: {FOLLOWUPS_BY_FIELD[f].question}'
        for f in sorted(LLM_SELECTABLE_FOLLOWUP_FIELDS)
    )
    prompt = (
        "You are tagging which known hazards apply to a home improvement "
        "task, for a safety triage system.\n\n"
        "HAZARDS YOU MAY TAG (choose ONLY from these ids):\n"
        f"{menu}\n\n"
        "QUESTIONS YOU MAY ASK (choose ONLY from these fields):\n"
        f"{question_menu}\n\n"
        "RULES:\n"
        "1. Do not invent ids or fields. Do not rate severity. Do not assign "
        "any risk level. Those are decided elsewhere.\n"
        "2. Every tag MUST quote, in its `evidence` field, the exact words "
        "from the task description that justify it. Copy them verbatim. A "
        "tag whose evidence is not found in the description is discarded, so "
        "an inferred hazard is the same as no hazard.\n"
        "3. NEVER infer facts the user did not state — not height, not "
        "access, not condition, not what else might be nearby. If the work "
        "is plainly hazardous ONLY IF some unstated fact holds, do not tag "
        "it: put the matching field in `ask` instead. That is what `ask` is "
        "for.\n"
        "4. TAG what is inherent to the work itself, even if the exact word "
        "is absent: replacing a light FITTING, a ceiling fan or a socket is "
        "work on fixed wiring. But a consumable that is designed to be "
        "user-replaced — a light BULB, a filter, a battery, a fuse in a plug "
        "— is NOT fixed-wiring work. Swapping one is not electrical work on "
        "the installation.\n"
        "5. Do not tag a hazard describing a different location, or a fault "
        "the description does not report. Work on a fitting is not work on "
        "the incoming supply or consumer unit. Wiring disconnected during "
        "routine work is not a live-conductor fault — that is for sparking, "
        "arcing or a wire found live, which the user would have said.\n\n"
        f"Task category: {category}\n"
        f"Task description: {description}\n\n"
        "Copy ids and fields EXACTLY as written above, character for "
        'character — "fixed_wiring_work", not "fixed_wiring". A value that '
        "is not an exact match is discarded. Return empty lists if nothing "
        "applies and nothing needs asking.\n\n"
        f"Valid hazard ids: {', '.join(sorted(VALID_RULE_IDS))}\n"
        f"Valid question fields: {', '.join(sorted(LLM_SELECTABLE_FOLLOWUP_FIELDS))}"
    )

    result = generate_structured(prompt, HazardTags)
    if result is None:
        logger.info("tag_hazards: no LLM result, falling back to keyword rules only")
        return None

    valid, invalid, unsupported = [], [], []
    for tag in result.tags or []:
        if tag.rule_id not in VALID_RULE_IDS:
            invalid.append(tag.rule_id)
        elif not _evidence_supports(description, tag.evidence):
            unsupported.append((tag.rule_id, tag.evidence[:80]))
        else:
            valid.append(tag.rule_id)

    if invalid:
        # A model returning ids outside the catalog is a model error, never a
        # new rule. Logged loudly because silent discards hide prompt drift.
        logger.warning(
            "tag_hazards: discarded %d id(s) outside the hardcoded catalog: %s",
            len(invalid),
            invalid,
        )
    if unsupported:
        # The model asserted a hazard it could not quote the user on. Logged
        # at warning because a rising rate here means the prompt is drifting
        # back toward inference.
        logger.warning(
            "tag_hazards: discarded %d ungrounded tag(s) (evidence not found "
            "in the description): %s",
            len(unsupported),
            unsupported,
        )

    ask_valid = [f for f in (result.ask or []) if f in LLM_SELECTABLE_FOLLOWUP_FIELDS]
    ask_invalid = [f for f in (result.ask or []) if f not in LLM_SELECTABLE_FOLLOWUP_FIELDS]
    if ask_invalid:
        logger.warning(
            "tag_hazards: discarded %d follow-up field(s) outside the " "selectable set: %s",
            len(ask_invalid),
            ask_invalid,
        )

    return TagResult(
        rule_ids=list(dict.fromkeys(valid)),
        ask_fields=list(dict.fromkeys(ask_valid)),
    )
