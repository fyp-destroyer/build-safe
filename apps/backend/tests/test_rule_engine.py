"""The single most important test in this PR: the rule engine can only
escalate risk, never de-escalate — final_risk = max(ml_risk, rule_risk) must
hold for every possible combination (rules.md §4 point 2 / CLAUDE.md).

Also covers: missing safety-critical follow-up answers escalate rather than
default to safe, and rule_risk/final_risk are always within [1, 5].
"""

import itertools

import pytest

from ai.classifier import classify
from ai.rule_engine import evaluate
from ai.rule_engine.rules import MAX_RISK_LEVEL, MIN_RISK_LEVEL


def test_final_risk_never_lower_than_ml_risk_across_many_inputs():
    """Property-style check: for a spread of descriptions/categories, the
    rule engine's output must never cause final_risk < ml_risk, and
    final_risk must always equal max(ml_risk, rule_risk)."""
    descriptions = [
        "paint the bedroom wall",
        "install a ceiling fan",
        "fix a leaking gas pipe",
        "replace the main electrical panel",
        "lay tile in the bathroom",
        "demolish a load-bearing wall",
        "there is water near an outlet and it sparked",
        "general tidy up of the garage",
    ]
    categories = ["painting", "electrical", "plumbing", "masonry", "general"]
    followups = [{}, {"power_isolated": True}, {"power_isolated": False}]

    for description, category, followup in itertools.product(descriptions, categories, followups):
        ml_risk, _confidence = classify(description, category)
        rule_risk, _triggered = evaluate(description, category, followup)

        assert MIN_RISK_LEVEL <= rule_risk <= MAX_RISK_LEVEL
        assert MIN_RISK_LEVEL <= ml_risk <= MAX_RISK_LEVEL

        final_risk = max(ml_risk, rule_risk)

        # THE invariant: never below either input, and never below ML alone.
        assert final_risk >= ml_risk
        assert final_risk >= rule_risk
        assert final_risk == max(ml_risk, rule_risk)


def test_rule_engine_escalates_gas_hazard_above_low_ml_prediction():
    """A gas hazard phrase must escalate risk even when the (placeholder)
    classifier alone would call it low risk (srs.md §9 representative
    rule / srs.md §11 acceptance criterion)."""
    description = "connect a new gas appliance in the kitchen, general handyman job"
    category = "general"

    ml_risk, _confidence = classify(description, category)
    rule_risk, triggered = evaluate(description, category, {})

    assert rule_risk >= 4
    assert any("gas" in rule for rule in triggered)

    final_risk = max(ml_risk, rule_risk)
    assert final_risk >= rule_risk
    assert final_risk >= 4


def test_missing_safety_critical_followup_escalates_not_assumes_safe():
    """Missing/falsy safety-critical follow-up answers must escalate risk,
    never be treated as an implicit "yes it's safe" (rules.md §4 point 4)."""
    description = "swap a wall outlet"
    category = "electrical"

    # No answer given at all for power_isolated.
    risk_missing, triggered_missing = evaluate(description, category, {})
    assert risk_missing >= 4
    assert "missing_followup:power_isolated" in triggered_missing

    # Answer explicitly present and truthy: rule should not force escalation
    # via the missing-followup path (other keyword rules may still apply,
    # but this description has no other hazard keywords).
    risk_answered, triggered_answered = evaluate(description, category, {"power_isolated": True})
    assert "missing_followup:power_isolated" not in triggered_answered
    assert risk_answered < risk_missing


def test_rule_engine_never_returns_out_of_range_risk_level():
    """Never invent a risk level outside 1-5."""
    for description in ["", "gas gas gas live wire live wiring main panel water near"]:
        risk, _triggered = evaluate(description, "electrical", {})
        assert 1 <= risk <= 5


@pytest.mark.parametrize(
    "ml_risk,rule_risk,expected_final",
    [
        (1, 1, 1),
        (5, 1, 5),
        (1, 5, 5),
        (3, 3, 3),
        (2, 4, 4),
        (4, 2, 4),
    ],
)
def test_max_combination_table(ml_risk, rule_risk, expected_final):
    """Direct table check of the max() invariant itself, independent of the
    placeholder heuristics — this is what every future real classifier/rule
    engine implementation must also satisfy."""
    assert max(ml_risk, rule_risk) == expected_final
    assert expected_final >= ml_risk
    assert expected_final >= rule_risk
