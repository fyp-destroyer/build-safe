"""Deterministic safety rule engine (Phase 5).

Evaluates a job's context against the hardcoded catalog in `catalog.py` and
returns an escalation floor. This module contains the LOGIC; `catalog.py`
holds the DATA. No hazard may be defined anywhere else.

THE ONE INVARIANT THIS MODULE MUST NEVER BREAK
----------------------------------------------
Rules only ever escalate. `evaluate()` returns a floor derived purely from
matched rules, defaulting to MIN_RISK_LEVEL when nothing matches; it has no
code path that lowers anything. Callers compute:

    final_risk = max(ml_risk, rule_risk)

so a rule can raise a low ML prediction but can never pull a high one down
(rules.md §4.2, srs.md §8.1, NFR-03).

WHAT THE LLM MAY AND MAY NOT DO HERE
------------------------------------
`llm_assist.tag_hazards()` may propose which EXISTING catalog rule ids apply
to a free-text description. That is the whole of its authority. It cannot
invent a rule, cannot set or suggest a risk number, and cannot change a
floor. Every id it returns is filtered against `catalog.VALID_RULE_IDS`
before it can influence anything, so a hallucinated or malicious id is
silently discarded (rules.md §4.1). LLM tagging is additive only: it can
cause a rule to fire that keywords missed, never suppress one that matched.
"""

from __future__ import annotations

import logging

from ai.rule_engine.catalog import (
    FOLLOWUPS,
    FOLLOWUPS_BY_FIELD,
    MAX_RISK_LEVEL,
    MIN_RISK_LEVEL,
    RULES,
    VALID_RULE_IDS,
    Rule,
)

logger = logging.getLogger(__name__)

__all__ = [
    "evaluate",
    "explain",
    "required_followups",
    "next_followup",
    "MIN_RISK_LEVEL",
    "MAX_RISK_LEVEL",
]


def _matches(rule: Rule, text: str, category: str, skill: str) -> bool:
    if rule.categories and category not in rule.categories:
        return False
    if rule.requires_skill and skill not in rule.requires_skill:
        return False
    if not any(k in text for k in rule.keywords):
        return False
    if any(x in text for x in rule.excludes):
        return False
    return True


def matched_rule_ids(
    description: str,
    category: str,
    llm_hazard_ids: list[str] | None = None,
    user_skill: str | None = None,
) -> list[str]:
    """Which catalog rules fire for this job, keyword and LLM paths combined.

    The LLM contribution is filtered against the closed catalog first. Any id
    outside it is dropped and logged - it is a model error, never a new rule.
    """
    text = f"{description} {category}".lower()
    cat = (category or "").lower()
    skill = (user_skill or "").strip().lower()

    fired = [r.id for r in RULES.values() if _matches(r, text, cat, skill)]

    if llm_hazard_ids:
        unknown = [i for i in llm_hazard_ids if i not in VALID_RULE_IDS]
        if unknown:
            logger.warning(
                "rule_engine: discarding %d LLM-proposed rule id(s) outside the "
                "hardcoded catalog: %s",
                len(unknown),
                unknown,
            )
        fired += [i for i in llm_hazard_ids if i in VALID_RULE_IDS]

    # De-duplicate, preserving order (two keywords can map to one rule).
    return list(dict.fromkeys(fired))


def required_followups(
    description: str,
    category: str,
    llm_hazard_ids: list[str] | None = None,
    user_skill: str | None = None,
) -> list[str]:
    """Safety-critical follow-up fields that apply to this job.

    Driven by which hazard rules fired, not by category alone: a task can
    need `power_isolated` without being category `electrical` (chasing a wall
    before tiling, wiring a thermostat). Category is a fallback trigger only.
    """
    fired = set(matched_rule_ids(description, category, llm_hazard_ids, user_skill))
    cat = (category or "").lower()
    out = []
    for f in FOLLOWUPS:
        by_rule = bool(set(f.applies_when_rule) & fired)
        by_category = cat in f.applies_to_categories
        if by_rule or by_category:
            out.append(f.field)
    return out


def next_followup(
    description: str,
    category: str,
    answers: dict,
    llm_hazard_ids: list[str] | None = None,
    user_skill: str | None = None,
) -> str | None:
    """The next unanswered safety-critical field, or None if all are answered.

    Presence, not truthiness: an explicit `False` is an ANSWER (the user said
    "no"), and must not be re-asked forever. Conflating the two once made the
    entire dangerous-task path unreachable - see memory.md, 2026-07-19.
    """
    answers = answers or {}
    for f in required_followups(description, category, llm_hazard_ids, user_skill):
        if f not in answers:
            return f
    return None


def evaluate(
    description: str,
    category: str,
    followup_answers: dict,
    llm_hazard_ids: list[str] | None = None,
    user_skill: str | None = None,
) -> tuple[int, list[str]]:
    """Return (rule_risk_level, triggered_rule_names).

    `rule_risk_level` is always within [MIN_RISK_LEVEL, MAX_RISK_LEVEL] and
    defaults to MIN_RISK_LEVEL when nothing matches. This function never
    lowers anything - it proposes an escalation floor and nothing more.
    """
    answers = followup_answers or {}
    triggered: list[str] = []
    risk = MIN_RISK_LEVEL

    fired = matched_rule_ids(description, category, llm_hazard_ids, user_skill)
    for rule_id in fired:
        triggered.append(rule_id)
        risk = max(risk, RULES[rule_id].floor)

    # Safety-critical follow-ups. Missing and denied are DIFFERENT states and
    # escalate differently; see catalog.FOLLOWUPS for why missing scores
    # higher than an explicit "no".
    for field in required_followups(description, category, llm_hazard_ids, user_skill):
        spec = FOLLOWUPS_BY_FIELD[field]
        if field not in answers:
            triggered.append(f"missing_followup:{field}")
            risk = max(risk, spec.floor_when_missing)
        elif answers[field] is False:
            triggered.append(f"unsafe_followup:{field}")
            risk = max(risk, spec.floor_when_denied)

    risk = min(max(risk, MIN_RISK_LEVEL), MAX_RISK_LEVEL)
    return risk, list(dict.fromkeys(triggered))


def explain(triggered: list[str]) -> list[str]:
    """Templated, hardcoded explanation text for triggered rules.

    Deliberately templated rather than LLM-generated: rules.md §4 permits the
    LLM to phrase explanations, but the safety content itself is fixed here so
    it cannot drift or be hallucinated. Unknown ids are skipped rather than
    guessed at.
    """
    out: list[str] = []
    for name in triggered:
        if name.startswith("missing_followup:"):
            field = name.split(":", 1)[1]
            spec = FOLLOWUPS_BY_FIELD.get(field)
            if spec:
                out.append(
                    f"A safety-critical question was not answered "
                    f'("{spec.question}"). Because that cannot be ruled out, '
                    f"this task is treated as the worst plausible case."
                )
        elif name.startswith("unsafe_followup:"):
            field = name.split(":", 1)[1]
            spec = FOLLOWUPS_BY_FIELD.get(field)
            if spec:
                out.append(
                    f"You indicated a safety-critical condition is not met "
                    f'("{spec.question}" — answered no), which raises the risk '
                    f"of this task."
                )
        elif name in RULES:
            out.append(RULES[name].explanation)
    return out
