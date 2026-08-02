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
from ai.rule_engine.catalog import (
    FOLLOWUPS,
    FOLLOWUPS_BY_FIELD,
    HARD_GATE_RULE_IDS,
    LLM_SELECTABLE_FOLLOWUP_FIELDS,
    MAX_RISK_LEVEL,
    MIN_RISK_LEVEL,
    RULES,
    VALID_RULE_IDS,
)
from ai.rule_engine.llm_assist import HazardTag, HazardTags, tag_hazards, tag_hazards_result

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
    reply = HazardTags(
        tags=[
            HazardTag(rule_id="active_gas_or_co", evidence="smell of gas"),
            HazardTag(rule_id="made_up_hazard", evidence="smell of gas"),
            HazardTag(rule_id="DROP TABLE", evidence="smell of gas"),
        ]
    )
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


# ------------------------------------------------------- evidence grounding
def test_tag_without_evidence_in_the_description_is_discarded():
    """THE bulb regression (observed live, 2026-08-01).

    "how do i change my light bulb" was returned as `fixed_wiring_work` +
    `work_at_height` and assessed at level 3. Neither rule keyword-matches;
    both came from the tagger, which reasoned bulb -> ceiling -> overhead ->
    height and wiring from a fitting it was never told about.

    A tag now has to quote the user. The model cannot quote words the user
    never wrote, so an inferred hazard is dropped mechanically instead of
    being argued out of it in the prompt.
    """
    description = "how do i change my light bulb"
    reply = HazardTags(
        tags=[
            # Nothing in the description mentions height at all.
            HazardTag(rule_id="work_at_height", evidence="the ceiling is high up"),
            HazardTag(rule_id="fixed_wiring_work", evidence="rewiring the fitting"),
        ]
    )
    with patch("ai.rule_engine.llm_assist.generate_structured", return_value=reply):
        assert tag_hazards(description, "electrical") == []

    # ...and end to end, the task comes back at the floor, not at 3.
    risk, triggered = evaluate(description, "electrical", {}, [], user_skill="Beginner")
    assert risk == MIN_RISK_LEVEL, f"a bulb swap should not escalate, got {risk}: {triggered}"


def test_evidence_matching_ignores_case_and_whitespace_only():
    """Trivial reformatting of an honest quote must not reject it — but
    nothing beyond that is relaxed."""
    description = "I need to  Rewire   the consumer unit"
    reply = HazardTags(
        tags=[HazardTag(rule_id="supply_side_electrical", evidence="rewire the CONSUMER unit")]
    )
    with patch("ai.rule_engine.llm_assist.generate_structured", return_value=reply):
        assert tag_hazards(description, "electrical") == ["supply_side_electrical"]


def test_llm_may_only_ask_for_followups_in_the_closed_set():
    """`ask` is selection from a fixed catalog, not question invention."""
    reply = HazardTags(
        tags=[],
        ask=["height_access", "is_the_user_feeling_lucky", "power_isolated"],
    )
    with patch("ai.rule_engine.llm_assist.generate_structured", return_value=reply):
        result = tag_hazards_result("change a bulb in the stairwell", "electrical")

    assert result is not None
    assert result.ask_fields == ["height_access", "power_isolated"]
    assert "is_the_user_feeling_lucky" not in result.ask_fields


def test_llm_asked_followups_are_additive_only():
    """The LLM can widen the question set; it can never narrow the one the
    catalog derived from fired hazards."""
    desc, cat = "replace a wall outlet", "electrical"
    derived = required_followups(desc, cat)
    assert "power_isolated" in derived

    widened = required_followups(desc, cat, llm_asked_fields=["height_access"])
    assert set(derived) <= set(widened)
    assert "height_access" in widened


# --------------------------------------------- LLM tags obey catalog gates
def test_llm_tag_cannot_bypass_a_rules_exclude_list():
    """Regression (2026-08-01): an LLM-proposed id used to skip `_matches`
    entirely, so `excludes`, `categories` and `requires_skill` applied to
    keyword matches only. `work_at_height` excludes "step ladder" and an LLM
    tag ignored it."""
    desc, cat = "reach the vent from a step ladder in the hallway", "general"
    _, triggered = evaluate(desc, cat, {}, llm_hazard_ids=["work_at_height"])
    assert "work_at_height" not in triggered


def test_llm_tag_cannot_bypass_an_exclude_list():
    """An LLM-proposed id is held to the same conditions as a keyword match.

    Before 2026-08-01 the LLM path checked catalog membership and nothing
    else, so `excludes`, `categories` and `requires_skill` applied to keyword
    matches only. `work_at_height` lists "step ladder" in its excludes and an
    LLM tag ignored it.

    `excludes` is the gate exercised here because it is the only one any rule
    currently uses: `requires_skill` lost its last user when
    `electrical_work_by_beginner` was deleted (2026-08-02), and no rule sets
    `categories`. Both remain supported on `Rule` and are still enforced by
    `_gates_allow`.
    """
    excluding = [r for r in RULES.values() if r.excludes]
    assert excluding, "no rule with excludes left to exercise this path"
    rule = excluding[0]
    veto = rule.excludes[0]

    _, blocked = evaluate(f"a task mentioning {veto}", "general", {}, [rule.id])
    _, allowed = evaluate("a task mentioning nothing in particular", "general", {}, [rule.id])
    assert rule.id not in blocked, f"{rule.id} fired despite its exclude {veto!r}"
    assert rule.id in allowed


# ------------------------------------------------------------------- gates
def test_unanswered_gate_still_fires_the_rule():
    """The safety property that makes gating sound: silence buys nothing.

    An unanswered gate leaves the hazard in force at its full floor, so the
    worst plausible case holds until the user actually rules it out.
    """
    desc, cat = "swap the bulb in the hallway", "electrical"
    risk, triggered = evaluate(desc, cat, {}, ["overhead_work_unknown_height"])
    assert "overhead_work_unknown_height" in triggered
    assert risk >= RULES["overhead_work_unknown_height"].floor


def test_confirmed_safe_gate_closes_the_rule_and_denied_does_not():
    desc, cat = "swap the bulb in the hallway", "electrical"
    tags = ["overhead_work_unknown_height"]

    _, confirmed = evaluate(desc, cat, {"height_access": True}, tags)
    _, denied = evaluate(desc, cat, {"height_access": False}, tags)
    _, missing = evaluate(desc, cat, {}, tags)

    assert "overhead_work_unknown_height" not in confirmed
    assert "overhead_work_unknown_height" in denied
    assert "overhead_work_unknown_height" in missing


def test_gating_never_lowers_risk_below_an_ungated_hazard():
    """A gate refines a trigger; it must not reach past its own rule.

    Answering the height question cannot touch a gas or wiring hazard that
    fired for unrelated reasons — that would be de-escalation wearing a
    gate's clothes.
    """
    desc, cat = "smell of gas while changing a bulb", "electrical"
    ungated, _ = evaluate(desc, cat, {}, ["overhead_work_unknown_height"])
    gated, triggered = evaluate(
        desc, cat, {"height_access": True}, ["overhead_work_unknown_height"]
    )

    assert "active_gas_or_co" in triggered
    assert gated >= RULES["active_gas_or_co"].floor
    assert ungated >= gated  # the gate may only remove its own rule's floor


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


# --------------------------------------------- hazard-family coverage (2026-08-01)
@pytest.mark.parametrize(
    "desc,category,expected_rule",
    [
        # Each of these returned level 1 — "Safe DIY" — before the six missing
        # hazard families were added. Measured, not hypothetical: see the
        # catalog comment above the 2026-08-01 block.
        (
            "my extension lead is hot to touch when the heater is on",
            "electrical",
            "appliance_flex_overload",
        ),
        (
            "burning off paint on the window frames with a blowtorch",
            "painting",
            "hot_works_ignition",
        ),
        (
            "apply a solvent based epoxy floor coating in a closed garage",
            "general",
            "flammable_vapour_enclosed",
        ),
        (
            "recharge the refrigerant in a split system air conditioner",
            "hvac",
            "refrigerant_circuit_work",
        ),
        ("fell a large mature tree close to the house", "general", "tree_felling"),
        ("dry cut paving slabs for the new patio", "masonry", "silica_dust"),
        (
            "sanding the old paint off a victorian window frame",
            "painting",
            "lead_paint_disturbance",
        ),
        ("sewage is backing up through the shower drain", "plumbing", "sewage_contamination"),
        ("cut the worktop with a circular saw", "carpentry", "powered_cutting_tool"),
        ("move a cast iron bath out of the upstairs bathroom", "plumbing", "heavy_manual_handling"),
        (
            "replace the pressure relief valve on a sealed central heating system",
            "plumbing",
            "pressurised_hot_water_system",
        ),
        (
            "replace the immersion heater element in the hot water cylinder",
            "plumbing",
            "pressurised_hot_water_system",
        ),
    ],
)
def test_previously_uncovered_hazards_now_fire(desc, category, expected_rule):
    _, triggered = evaluate(desc, category, {}, None, user_skill="Some experience")
    assert expected_rule in triggered, f"{expected_rule} did not fire for {desc!r}"


def test_every_dataset_hazard_family_has_at_least_one_rule():
    """The audit that found six empty families, kept as a standing check.

    A hazard family the dataset uses but the catalog has no rule for is not a
    neutral gap: the LLM tagger can only select from the catalog, so it routes
    those tasks to the nearest rule that DOES exist. That is how a blowtorch
    came back tagged `asbestos_disturbance` — the model was picking the best
    option from a menu that did not contain the right answer.
    """
    import json
    from pathlib import Path

    data_dir = Path(__file__).resolve().parents[3] / "ml" / "data"
    if not data_dir.exists():  # pragma: no cover - ml/ absent in some checkouts
        pytest.skip("ml/data not present")

    used: set[str] = set()
    for split in ("train", "val", "test"):
        path = data_dir / f"{split}.json"
        if path.exists():
            for row in json.loads(path.read_text(encoding="utf-8")):
                used.update(row["hazards"])
    used.discard("none")

    covered = {rule.hazard for rule in RULES.values()}
    missing = sorted(used - covered)
    assert not missing, f"dataset hazard families with no catalog rule: {missing}"


def test_new_rules_did_not_start_escalating_benign_tasks():
    """The catalog's value is that it almost never false-fires.

    Adding twelve rules cost 3 over-escalations across 242 low-risk dataset
    rows; this pins the everyday cases so a future keyword loosened into a
    single common word cannot quietly spend that advantage.
    """
    benign = [
        ("change a light bulb in the kitchen", "electrical"),
        ("paint a bedroom wall with a roller", "painting"),
        ("hang a picture frame on the living room wall", "carpentry"),
        ("assemble a flat pack wardrobe", "carpentry"),
        ("put up a curtain pole above the window", "carpentry"),
        ("replace the washer in a dripping tap", "plumbing"),
    ]
    for desc, category in benign:
        risk, triggered = evaluate(desc, category, {}, None, user_skill="Beginner")
        assert risk == MIN_RISK_LEVEL, f"{desc!r} escalated to {risk} via {triggered}"


def test_noise_rule_advises_without_escalating():
    """`sustained_noise_exposure` has floor 1 on purpose.

    Hearing damage does not change WHO should attempt a task, so escalating
    for it would be wrong under the competence ladder — but the user should
    still be told. A floor of MIN_RISK_LEVEL is how the catalog expresses
    "worth saying, not worth escalating": the rule fires, reaches explain(),
    and moves nothing.
    """
    risk, triggered = evaluate(
        "hire a jackhammer to break up the concrete path",
        "masonry",
        {},
        None,
        user_skill="Some experience",
    )
    assert "sustained_noise_exposure" in triggered
    assert explain(["sustained_noise_exposure"]), "a fired rule must still explain itself"
    risk_without = evaluate("break up the path", "masonry", {}, None)[0]
    assert risk >= risk_without


# ------------------------------------------------------------ catalog health
def test_catalog_is_internally_consistent():
    for rule in RULES.values():
        assert MIN_RISK_LEVEL <= rule.floor <= MAX_RISK_LEVEL
        assert rule.explanation.strip(), f"{rule.id} has no explanation"
        assert rule.id in VALID_RULE_IDS
        # A keyword-less rule is LLM-tag-only, which is allowed but only
        # when it is gated: nothing in the text can trigger it, so the sole
        # check on an over-eager tag is a question the user can answer.
        # Ungated AND keyword-less would be a rule that fires on the model's
        # say-so alone with no way to contest it.
        assert rule.keywords or rule.gated_by, (
            f"{rule.id} has neither keywords nor a gate: it can only ever fire "
            f"on an unchallengeable LLM tag"
        )


def test_gates_reference_real_followup_fields():
    for rule in RULES.values():
        for field in rule.gated_by:
            assert (
                field in FOLLOWUPS_BY_FIELD
            ), f"{rule.id} is gated by unknown follow-up field {field!r}"
            # The gate must be reachable: something has to ask the question,
            # or the rule fires forever with no way to close it.
            spec = FOLLOWUPS_BY_FIELD[field]
            assert (
                rule.id in spec.applies_when_rule or field in LLM_SELECTABLE_FOLLOWUP_FIELDS
            ), f"{rule.id}'s gate {field!r} is never asked for, so it can never close"


def test_catastrophic_hazards_can_never_be_gated_away():
    """A user answer must not be able to dismiss the hazards that kill.

    `gated_by` is right for facts the user is authoritative about ("can you
    reach it from the floor?"). It is wrong for a suspected gas escape, a
    live conductor or asbestos: people are poor judges of those, and being
    wrong is fatal. Enforced here so a future edit cannot quietly add one.
    """
    for rule_id in HARD_GATE_RULE_IDS:
        assert rule_id in RULES, f"HARD_GATE_RULE_IDS names unknown rule {rule_id}"
        assert not RULES[
            rule_id
        ].gated_by, f"{rule_id} is catastrophic and must not be gateable by a user answer"


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
    requires, and a category-gated rule needs its category. Keyword-less
    rules are LLM-tag-only, so they are fired through that path instead.
    """
    rule = RULES[rule_id]
    cat = rule.categories[0] if rule.categories else "general"
    skill = rule.requires_skill[0] if rule.requires_skill else "Experienced"
    if rule.keywords:
        _, triggered = evaluate(rule.keywords[0], cat, {}, user_skill=skill)
        assert rule_id in triggered, f"{rule_id} never fires on its own first keyword"
    else:
        _, triggered = evaluate("some task", cat, {}, [rule_id], user_skill=skill)
        assert rule_id in triggered, f"{rule_id} never fires even when tagged"


def test_fixed_wiring_carries_the_professional_recommended_floor_for_everyone():
    """srs.md §9's intent, after `user_skill` was removed (2026-08-02).

    The rule used to read "electrical wiring task + beginner user -> at least
    Professional Recommended", implemented as `electrical_work_by_beginner`
    (floor 3) stacked on `fixed_wiring_work` (floor 2). With the skill field
    gone, `fixed_wiring_work` carries floor 3 directly: beginners land
    exactly where they did, and the outcome no longer depends on an
    unverifiable self-report (srs.md §3).
    """
    desc, cat = "replace a light switch", "electrical"
    risk, triggered = evaluate(desc, cat, {"power_isolated": True})

    assert "fixed_wiring_work" in triggered
    assert risk >= 3, "fixed wiring must still reach Professional Recommended"
    # And it must not depend on who is asking any more.
    for skill in ("Beginner", "Some experience", "Experienced", "", None):
        assert evaluate(desc, cat, {"power_isolated": True}, user_skill=skill)[0] == risk


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
