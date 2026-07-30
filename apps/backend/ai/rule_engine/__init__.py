"""Hardcoded hazard rubric (Phase 5 — real, no longer a placeholder).

`catalog.py` holds the DATA: every hazard rule, its escalation floor, and its
explanation text. `rules.py` holds the LOGIC that evaluates it. No hazard may
be defined anywhere else, and there is deliberately no `safety_rules` table,
no admin UI and no runtime edit path — changing a rule is a code change and a
code review (srs.md §2.5, rules.md §4).

Two invariants this package exists to guarantee:

  * final_risk = max(ML, rules). Rules only ever escalate; nothing here can
    lower a risk level (rules.md §4.2, srs.md NFR-03).
  * The LLM may only SELECT ids from the hardcoded catalog when tagging
    hazards. It cannot invent a rule, assign a risk number or change a floor;
    every id it returns is filtered against `catalog.VALID_RULE_IDS`
    (rules.md §4.1).

Both are enforced by tests in `tests/test_rule_catalog.py`.
"""

from ai.rule_engine.rules import (
    MAX_RISK_LEVEL,
    MIN_RISK_LEVEL,
    evaluate,
    explain,
    next_followup,
    required_followups,
)

__all__ = [
    "evaluate",
    "explain",
    "required_followups",
    "next_followup",
    "MIN_RISK_LEVEL",
    "MAX_RISK_LEVEL",
]
