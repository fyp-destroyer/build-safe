"""Hardcoded hazard rubric — implemented in Phase 5. IMPORTANT: final_risk =
max(ML, rules); rules only ever escalate risk, never de-escalate. No
admin-editable rules table by design.

`evaluate()` in rules.py is a TEMPORARY placeholder (keyword rules only, no
LLM hazard classifier), not the real srs.md §9 catalog. See rules.py's
module docstring.
"""

from ai.rule_engine.rules import evaluate

__all__ = ["evaluate"]
