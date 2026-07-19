"""TEMPORARY placeholder for Phase 5. NOT the real safety rule catalog from
srs.md §9. Real implementation must replace this before Phase 5's exit check
(rules.md §4.2) can pass. Do not treat this as production-safe.

This module exists only to prove the `final_risk = max(ML, rules)` wiring
and the "missing safety-critical info escalates" invariant work end-to-end.
It is a small hardcoded list of keyword-based rules, NOT the reviewed hazard
catalog (srs.md §9) and NOT an LLM-assisted hazard classifier
(architecture.md §4 step 4 / rules.md §4.1) — no LLM is called here at all.

The one hard invariant this module (and every future replacement of it)
MUST uphold: rules only ever escalate risk, never de-escalate. Callers
compute `final_risk = max(ml_risk, rule_risk)`; this module never returns a
risk level with the intent of lowering anything.
"""

# (keyword substring, minimum resulting risk level) — checked against the
# lowercased description + category. Order doesn't matter; all matching
# rules are collected and the highest resulting level wins.
_KEYWORD_RULES: tuple[tuple[str, str, int], ...] = (
    ("gas_hazard", "gas", 4),
    ("gas_hazard", "gas leak", 5),
    ("gas_hazard", "gas appliance", 4),
    ("electrical_panel_hazard", "electrical panel", 4),
    ("electrical_panel_hazard", "main panel", 4),
    ("live_wire_hazard", "live wire", 4),
    ("live_wire_hazard", "live wiring", 4),
    ("load_bearing_hazard", "load-bearing", 4),
    ("load_bearing_hazard", "load bearing", 4),
    ("water_near_electrical_hazard", "water near", 5),
)

# Follow-up fields considered safety-critical: if the answer is missing or
# falsy, treat as the worst plausible case (escalate), never assume safety.
_SAFETY_CRITICAL_FOLLOWUPS: tuple[tuple[str, int], ...] = (
    ("power_isolated", 4),  # e.g. "is the circuit isolated/breaker off?"
    ("load_bearing_confirmed", 4),  # e.g. "confirmed NOT load-bearing?"
    ("gas_line_present", 4),  # e.g. "confirmed no gas line nearby?"
)

MIN_RISK_LEVEL = 1
MAX_RISK_LEVEL = 5


def evaluate(description: str, category: str, followup_answers: dict) -> tuple[int, list[str]]:
    """Evaluate placeholder keyword rules against a job's context.

    Returns (rule_risk_level, triggered_rule_names). `rule_risk_level` is
    always in [1, 5]. Defaults to 1 (no escalation) when nothing matches —
    callers MUST still take max(ml_risk, rule_risk); this function never
    lowers anything, it only ever proposes an escalation floor.

    Missing/falsy safety-critical follow-up answers escalate risk rather
    than being treated as "safe" (rules.md §4 point 4 / CLAUDE.md).
    """
    text = f"{description} {category}".lower()

    triggered: list[str] = []
    risk = MIN_RISK_LEVEL

    for rule_name, keyword, resulting_level in _KEYWORD_RULES:
        if keyword in text:
            triggered.append(rule_name)
            risk = max(risk, resulting_level)

    for field, escalation_level in _SAFETY_CRITICAL_FOLLOWUPS:
        if field in _relevant_followups_for(category) and not followup_answers.get(field):
            rule_name = f"missing_followup:{field}"
            triggered.append(rule_name)
            risk = max(risk, escalation_level)

    risk = min(max(risk, MIN_RISK_LEVEL), MAX_RISK_LEVEL)
    # De-duplicate while preserving order: multiple keywords can map to the
    # same rule_name (e.g. "gas" and "gas leak" both -> "gas_hazard"), which
    # would otherwise list a rule as triggered twice — cosmetic only, never
    # affects `risk` since max() is idempotent either way.
    triggered = list(dict.fromkeys(triggered))
    return risk, triggered


def _relevant_followups_for(category: str) -> set[str]:
    """Which safety-critical follow-up fields apply to a given category.

    Placeholder mapping — the real per-category follow-up schema is out of
    scope for this pass (noted as free-form JSON on Job.followup_answers
    until Phase 5).
    """
    category = category.lower()
    if category == "electrical":
        return {"power_isolated"}
    if category in {"masonry", "carpentry"}:
        return {"load_bearing_confirmed"}
    if category == "plumbing":
        return {"gas_line_present"}
    return set()
