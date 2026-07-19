"""LLM-assisted category tagging + follow-up question phrasing.

**What this module is allowed to do, and nothing more** (rules.md §4 /
CLAUDE.md): (a) pick a category string from the fixed, closed 9-value
`TASK_CATEGORIES` set for a free-text task description ("tagging"), and
(b) phrase the natural-language wording of a question about an
*already-hardcoded* follow-up field. It never decides which follow-up fields
are required for a category, and never decides whether a missing answer
escalates risk — that logic is 100% hardcoded and lives entirely in
`ai/rule_engine/rules.py` (`_SAFETY_CRITICAL_FOLLOWUPS`,
`_relevant_followups_for`) and `services/job_service.py`
(`_REQUIRED_FOLLOWUPS_BY_CATEGORY`). This module is never consulted for, and
has no way to influence, risk level, rule triggering, or which fields are
required.

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
