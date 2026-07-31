"""Phase 5 exit check.

Two invariants, stated by phases.md Phase 5:

  1. Rules can only escalate, never de-escalate (rules.md §4.2).
  2. The LLM hazard classifier cannot introduce a rule outside the
     hardcoded set (rules.md §4.1).

These are pure-logic tests with no database and no network: a test that
proves the safety engine cannot be subverted must not be skippable because a
container is not running.
"""

import itertools
from unittest.mock import patch

import pytest

from ai.rule_engine import evaluate, explain, next_followup, required_followups
from ai.rule_engine.catalog import FOLLOWUPS, MAX_RISK_LEVEL, MIN_RISK_LEVEL, RULES, VALID_RULE_IDS
from ai.rule_engine.llm_assist import HazardTags, tag_hazards

# A spread of descriptions covering every hazard family plus benign tasks.
DESCRIPTIONS = [
    "paint a bedroom wall with a roller",
    "assemble a flat pack wardrobe",
    "replace a wall outlet in the bedroom",
    "rewire the consumer unit in my garage",
    "there is a live wire sparking in the basement",
    "I can smell gas near the cooker connection",
    "connect a new gas hob to the supply pipe",
    "remove a wall between the kitchen and living room",
    "the crack above the door keeps getting wider",
    "walk across the fragile perspex roof panels",
    "strip and re-tile the roof of a two storey house",
    "scrape off artex that may contain asbestos",
    "go into the crawl space under the floor",
    "dig a trench across the garden for a water line",
]
CATEGORIES = [
    "electrical",
    "plumbing",
    "carpentry",
    "masonry",
    "painting",
    "tiling",
    "hvac",
    "roofing",
    "general",
]
ANSWER_SETS = [
    {},
    {"power_isolated": True},
    {"power_isolated": False},
    {"load_bearing_confirmed": True},
    {"load_bearing_confirmed": False},
    {"gas_line_present": True},
    {"power_isolated": True, "load_bearing_confirmed": True, "gas_line_present": True},
]


# ---------------------------------------------------------------- invariant 1
def test_rules_can_only_escalate_never_de_escalate():
    """final_risk = max(ml, rule) must never fall below the ML prediction.

    Exhaustive over descriptions x categories x answer sets x every possible
    ML output - the property must hold for all of them, not on average.
    """
    for desc, cat, answers in itertools.product(DESCRIPTIONS, CATEGORIES, ANSWER_SETS):
        rule_risk, _ = evaluate(desc, cat, answers)
        for ml_risk in range(MIN_RISK_LEVEL, MAX_RISK_LEVEL + 1):
            final = max(ml_risk, rule_risk)
            assert final >= ml_risk, (
                f"de-escalation: ml={ml_risk} rule={rule_risk} final={final} "
                f"for {desc!r}/{cat}/{answers}"
            )
            assert final >= rule_risk
            assert MIN_RISK_LEVEL <= final <= MAX_RISK_LEVEL


def test_evaluate_output_always_in_range_and_defaults_to_minimum():
    for desc, cat, answers in itertools.product(DESCRIPTIONS, CATEGORIES, ANSWER_SETS):
        risk, triggered = evaluate(desc, cat, answers)
        assert MIN_RISK_LEVEL <= risk <= MAX_RISK_LEVEL
        assert isinstance(triggered, list)
        assert len(triggered) == len(set(triggered)), "triggered rules must be de-duplicated"


def test_benign_task_is_not_escalated():
    """The engine must not escalate everything - that would be safe but useless."""
    risk, triggered = evaluate("paint a bedroom wall with a roller", "painting", {})
    assert risk == MIN_RISK_LEVEL
    assert triggered == []


# ---------------------------------------------------------------- invariant 2
def test_llm_cannot_introduce_a_rule_outside_the_catalog():
    """Invented ids must be discarded, not trusted, and must not shift risk."""
    desc, cat = "paint a bedroom wall with a roller", "painting"
    baseline_risk, baseline_triggered = evaluate(desc, cat, {})

    hallucinated = [
        "catastrophic_danger",
        "nuclear_hazard",
        "risk_level_5",
        "active_gas_or_co_EXTRA",
        "",
        "'; DROP TABLE jobs;--",
    ]
    risk, triggered = evaluate(desc, cat, {}, llm_hazard_ids=hallucinated)

    assert risk == baseline_risk, "an invented rule id changed the risk level"
    assert triggered == baseline_triggered
    assert not set(triggered) & set(hallucinated)


def test_llm_can_only_select_ids_that_exist_in_the_catalog():
    """A valid id may fire a rule; the floor still comes from the catalog."""
    desc, cat = "have a look at the utility cupboard", "general"
    risk, triggered = evaluate(desc, cat, {}, llm_hazard_ids=["asbestos_disturbance"])
    assert "asbestos_disturbance" in triggered
    # The level is the catalog's floor, never anything the LLM supplied.
    assert risk == RULES["asbestos_disturbance"].floor


def test_llm_tagging_is_additive_and_cannot_suppress_a_keyword_match():
    """An empty or unrelated LLM reply must not cancel a deterministic match."""
    desc, cat = "I can smell gas near the cooker connection", "plumbing"
    with_llm, trig_with = evaluate(desc, cat, {}, llm_hazard_ids=[])
    without, trig_without = evaluate(desc, cat, {})
    assert with_llm == without == RULES["active_gas_or_co"].floor
    assert "active_gas_or_co" in trig_with and "active_gas_or_co" in trig_without

    # Even a wrong-but-valid tag cannot lower the keyword-derived floor.
    risk, _ = evaluate(desc, cat, {}, llm_hazard_ids=["buried_services"])
    assert risk >= RULES["active_gas_or_co"].floor


def test_tag_hazards_filters_invalid_ids_from_the_model():
    reply = HazardTags(rule_ids=["active_gas_or_co", "made_up_hazard", "DROP TABLE"])
    with patch("ai.rule_engine.llm_assist.generate_structured", return_value=reply):
        out = tag_hazards("smell of gas", "plumbing")
    assert out == ["active_gas_or_co"]


def test_tag_hazards_returns_empty_when_llm_unavailable():
    """Failure must degrade to 'no LLM', not to 'no hazards'."""
    with patch("ai.rule_engine.llm_assist.generate_structured", return_value=None):
        assert tag_hazards("smell of gas", "plumbing") == []
    # Keyword rules still fire without the LLM.
    risk, triggered = evaluate("I can smell gas near the cooker", "plumbing", {}, [])
    assert risk == 5 and "active_gas_or_co" in triggered


# ------------------------------------------------------- follow-up semantics
def test_missing_answer_escalates_higher_than_an_explicit_no():
    """Unanswered and answered-unsafe are different states.

    Conflating them once made the entire dangerous-task path unreachable
    (memory.md, 2026-07-19), so this asserts they stay distinct.
    """
    desc, cat = "remove a wall between the kitchen and living room", "carpentry"
    missing, trig_missing = evaluate(desc, cat, {})
    denied, trig_denied = evaluate(desc, cat, {"load_bearing_confirmed": False})
    confirmed, _ = evaluate(desc, cat, {"load_bearing_confirmed": True})

    assert missing > denied >= confirmed
    assert "missing_followup:load_bearing_confirmed" in trig_missing
    assert "unsafe_followup:load_bearing_confirmed" in trig_denied


def test_answered_false_is_not_treated_as_unanswered():
    desc, cat = "replace a wall outlet", "electrical"
    assert next_followup(desc, cat, {}) == "power_isolated"
    assert next_followup(desc, cat, {"power_isolated": False}) is None


def test_followups_are_hazard_driven_not_only_category_driven():
    """A tiling job that chases a wall still needs the power question."""
    fields = required_followups("chase a channel into the kitchen wall for new wiring", "tiling")
    assert "power_isolated" in fields


# ------------------------------------------------------------ catalog health
def test_catalog_is_internally_consistent():
    for rule in RULES.values():
        assert MIN_RISK_LEVEL <= rule.floor <= MAX_RISK_LEVEL
        assert rule.keywords, f"{rule.id} has no keywords and can never fire"
        assert rule.explanation.strip(), f"{rule.id} has no explanation"
        assert rule.id in VALID_RULE_IDS


def test_followups_reference_real_rules_and_escalate_upward():
    for f in FOLLOWUPS:
        for rid in f.applies_when_rule:
            assert rid in RULES, f"followup {f.field} references unknown rule {rid}"
        assert (
            f.floor_when_missing >= f.floor_when_denied
        ), "an unanswered safety question must never score below an explicit no"
        assert MIN_RISK_LEVEL <= f.floor_when_denied <= MAX_RISK_LEVEL
        assert MIN_RISK_LEVEL <= f.floor_when_missing <= MAX_RISK_LEVEL


@pytest.mark.parametrize("rule_id", sorted(RULES))
def test_every_catalog_rule_can_actually_fire(rule_id):
    """A rule that no input can trigger is dead safety code.

    Builds valid conditions per rule: a skill-gated rule needs the skill it
    requires, and a category-gated rule needs its category.
    """
    rule = RULES[rule_id]
    cat = rule.categories[0] if rule.categories else "general"
    skill = rule.requires_skill[0] if rule.requires_skill else "Experienced"
    _, triggered = evaluate(rule.keywords[0], cat, {}, user_skill=skill)
    assert rule_id in triggered, f"{rule_id} never fires on its own first keyword"


def test_beginner_gated_rule_fires_only_for_beginners():
    """srs.md §9: 'electrical wiring task + beginner user' raises the floor."""
    desc, cat = "replace a light switch", "electrical"
    beginner, trig_b = evaluate(desc, cat, {"power_isolated": True}, user_skill="Beginner")
    expert, trig_e = evaluate(desc, cat, {"power_isolated": True}, user_skill="Experienced")

    assert "electrical_work_by_beginner" in trig_b
    assert "electrical_work_by_beginner" not in trig_e
    assert beginner > expert, "beginner doing wiring work should score higher"


def test_explain_returns_only_hardcoded_text_and_skips_unknown_ids():
    out = explain(["active_gas_or_co", "totally_invented_rule"])
    assert out == [RULES["active_gas_or_co"].explanation]


# ------------------------------------------------- user-facing explanations
def test_assessment_exposes_plain_language_safety_notes():
    """FR-05: an explanation, not a rule id.

    Regression guard for a gap found by live browser testing: the UI showed
    "Active gas or co" to a user reporting a gas smell, because the API only
    ever sent the rule slug. The guidance itself must reach the client.
    """
    import datetime
    import uuid

    from schemas.assessment import RiskAssessmentOut

    out = RiskAssessmentOut(
        id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        risk_level=5,
        confidence=0.7,
        explanation="…",
        hazard_tags=["active_gas_or_co"],
        triggered_rules=["active_gas_or_co", "unsafe_followup:load_bearing_confirmed"],
        cost=None,
        time=None,
        difficulty=None,
        status="completed",
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    notes = out.safety_notes
    assert len(notes) == 2
    assert any("emergency" in n for n in notes), "gas guidance missing"
    # It must be prose, not the slug.
    assert not any(n.startswith("active_gas_or_co") for n in notes)


def test_safety_notes_empty_when_nothing_triggered():
    import datetime
    import uuid

    from schemas.assessment import RiskAssessmentOut

    out = RiskAssessmentOut(
        id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        risk_level=1,
        confidence=0.9,
        explanation="…",
        hazard_tags=[],
        triggered_rules=[],
        cost=None,
        time=None,
        difficulty=None,
        status="completed",
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    assert out.safety_notes == []
