"""Validate ml/data/seed_examples.json against every rule documented in
ml/data/README.md.

Run: python ml/validate_dataset.py

Exits non-zero if any rule is violated. These are not style checks - each
one encodes a safety or consistency rule that was decided deliberately
(several after real mistakes were caught in review; see memory.md). Keep
this in sync with README.md whenever a rule changes.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

# Ceiling on how much `user_skill` may predict `risk_level`, as normalised
# mutual information. Not zero: with a few hundred rows some correlation
# arises by chance, and forcing exact independence would mean contorting
# `user_skill` values into implausible ones. 0.05 is loose enough to survive
# sampling noise and tight enough that the 0.35 the original seed data scored
# could never pass. Tighten as the corpus grows.
NMI_LIMIT = 0.05

DATA = Path(__file__).parent / "data" / "seed_examples.json"
GENERATED = Path(__file__).parent / "data" / "generated_examples.json"

CATEGORIES = {
    "electrical",
    "plumbing",
    "carpentry",
    "masonry",
    "painting",
    "tiling",
    "hvac",
    "roofing",
    "general",
}

SKILLS = {"Beginner", "Some experience", "Experienced"}

RISK_LABELS = {
    1: "safe_diy",
    2: "diy_with_supervision",
    3: "professional_recommended",
    4: "professional_required",
    5: "dangerous",
}

HAZARDS = {
    "electrical_shock",
    "fall_from_height",
    "structural_collapse",
    "gas_leak",
    "buried_utility_strike",
    "fire",
    "chemical_exposure",
    "cuts_lacerations",
    "respiratory_hazard",
    "asbestos_exposure",
    "water_damage",
    "burns",
    "heavy_object_handling",
    "hearing_damage",
    "confined_space",
    "none",
}

PROFESSIONAL_CATEGORIES = {
    "electrician",
    "plumber",
    "carpenter",
    "mason",
    "structural_engineer",
    "roofer",
    "hvac_technician",
    "general_contractor",
    None,
}

PPE = {
    "safety_glasses",
    "work_gloves",
    "insulated_gloves",
    "rubber_gloves",
    "dust_mask",
    "respirator_mask",
    "safety_harness",
    "hearing_protection",
    "knee_pads",
    "steel_toe_boots",
    "hard_hat",
}

# The three safety-critical hazard-confirmation fields. An unanswered one
# (answer: null) forces risk_level 5 - see README's escalation rule.
SAFETY_CRITICAL_FIELDS = {
    "power_isolated": (
        "Have you confirmed the power to this circuit is fully isolated at "
        "the breaker before starting?"
    ),
    "load_bearing_confirmed": (
        "Have you confirmed the wall or structure involved is NOT load-bearing?"
    ),
    "gas_line_present": (
        "Have you confirmed there is no gas line present near this work area?"
    ),
}

BASE_KEYS = {
    "id",
    "task_text",
    "category",
    "user_skill",
    "tools_available",
    "hazards",
    "risk_level",
    "risk_label",
    "professional_category",
    "suggested_ppe",
    "followup_questions",
    # Written by ml/assign_basis.py: the severity band, restriction class and
    # cited sources behind this label, per ml/data/rubric.md. Regenerated, never
    # hand-edited — edit the rubric or the source registry instead.
    "basis",
}

# Generated records additionally carry provenance, so a variant can always be
# traced to the seed it came from and to the rule that produced it.
GENERATED_KEYS = BASE_KEYS | {"variant_of", "generation_rule"}

# Weak-labeling rules permitted in generated_examples.json. WL-1* must
# preserve the parent label exactly; WL-2 must escalate to 5. Nothing may
# ever lower a parent's risk_level (rules.md 4.2).
LABEL_PRESERVING_RULES = {"WL-1a:rephrase", "WL-1b:room-substitution"}
ESCALATION_RULES = {"WL-2:strip-confirmation"}


def validate(examples: list[dict], *, generated: bool = False,
             parents: dict[str, dict] | None = None) -> list[str]:
    errors: list[str] = []

    def err(example: dict, msg: str) -> None:
        errors.append(f"{example.get('task_text', '<no task_text>')[:60]!r}: {msg}")

    seen_texts: set[str] = set()
    required = GENERATED_KEYS if generated else BASE_KEYS

    for e in examples:
        missing = required - set(e)
        extra = set(e) - required
        if missing:
            err(e, f"missing keys: {sorted(missing)}")
        if extra:
            err(e, f"unexpected keys: {sorted(extra)}")
        if missing:
            continue

        if e["task_text"] in seen_texts:
            err(e, "duplicate task_text")
        seen_texts.add(e["task_text"])

        if e["category"] not in CATEGORIES:
            err(e, f"invalid category {e['category']!r}")
        if e["user_skill"] not in SKILLS:
            err(e, f"invalid user_skill {e['user_skill']!r}")

        level = e["risk_level"]
        if level not in RISK_LABELS:
            err(e, f"invalid risk_level {level!r}")
        elif RISK_LABELS[level] != e["risk_label"]:
            err(e, f"risk_label {e['risk_label']!r} does not match risk_level {level}")

        bad_hazards = set(e["hazards"]) - HAZARDS
        if bad_hazards:
            err(e, f"unknown hazard tags: {sorted(bad_hazards)}")
        if "none" in e["hazards"] and len(e["hazards"]) > 1:
            err(e, "'none' hazard cannot be combined with other hazards")
        if not e["hazards"]:
            err(e, "hazards must not be empty (use ['none'])")

        if e["professional_category"] not in PROFESSIONAL_CATEGORIES:
            err(e, f"unknown professional_category {e['professional_category']!r}")

        bad_ppe = set(e["suggested_ppe"]) - PPE
        if bad_ppe:
            err(e, f"unknown PPE items: {sorted(bad_ppe)}")

        # Rule: risk_level 5 means "do not attempt" - never suggest PPE, which
        # would read as "here's how to do it yourself safely".
        if level == 5 and e["suggested_ppe"]:
            err(e, "risk_level 5 must have suggested_ppe: []")

        # Rule: levels 1-2 are DIY-appropriate, so no professional is named.
        if level in (1, 2) and e["professional_category"] is not None:
            err(e, f"risk_level {level} must have professional_category: null")
        if level >= 3 and e["professional_category"] is None:
            err(e, f"risk_level {level} must name a professional_category")

        unanswered_safety_critical = False
        for f in e["followup_questions"]:
            if set(f) != {"field", "question", "answer"}:
                err(e, f"followup has wrong keys: {sorted(f)}")
                continue
            if f["answer"] not in (True, False, None):
                err(e, f"followup answer must be true/false/null, got {f['answer']!r}")

            field = f["field"]
            if field in SAFETY_CRITICAL_FIELDS:
                if f["question"] != SAFETY_CRITICAL_FIELDS[field]:
                    err(e, f"{field} uses non-canonical question wording")
                if f["answer"] is None:
                    unanswered_safety_critical = True
            elif field.startswith("tool_available:"):
                tool = field.split(":", 1)[1]
                expected = f"Do you have a {tool.replace('_', ' ')} available for this task?"
                if f["question"] != expected:
                    err(e, f"{field} question should be {expected!r}")
            else:
                err(e, f"unknown followup field {field!r}")

        # Rule: an unanswered safety-critical follow-up means the worst
        # plausible case cannot be ruled out - escalate to the maximum.
        if unanswered_safety_critical and level != 5:
            err(e, f"unanswered safety-critical followup requires risk_level 5, got {level}")

        # Weak-labeling rules: a generated variant's label must be justified
        # by its stated rule, and may never come out lower than its parent.
        if generated:
            rule = e["generation_rule"]
            parent = (parents or {}).get(e["variant_of"])
            if parent is None:
                err(e, f"variant_of {e['variant_of']!r} does not match any seed id")
            elif rule in LABEL_PRESERVING_RULES:
                if level != parent["risk_level"]:
                    err(e, f"{rule} must preserve the parent label "
                           f"({parent['risk_level']}), got {level}")
            elif rule in ESCALATION_RULES:
                if level != 5:
                    err(e, f"{rule} must escalate to risk_level 5, got {level}")
                if not unanswered_safety_critical:
                    err(e, f"{rule} must leave a safety-critical followup unanswered")
            else:
                err(e, f"unknown generation_rule {rule!r}")
            if parent is not None and level < parent["risk_level"]:
                err(e, f"generated variant lowers risk below its parent "
                       f"({parent['risk_level']} -> {level}); de-escalation is never permitted")

        # Rule: a tool_available followup only makes sense when tools are
        # genuinely unknown.
        has_tool_followup = any(
            f.get("field", "").startswith("tool_available:") for f in e["followup_questions"]
        )
        if has_tool_followup and e["tools_available"]:
            err(e, "tool_available followup present but tools_available is non-empty")

    return errors


def check_skill_label_independence(rows: list[dict], *, label: str) -> list[str]:
    """`user_skill` must carry no information about `risk_level`.

    `risk_level` describes what the TASK demands (ml/data/README.md, "5 risk
    levels"); who happens to be asking must not move it. This check exists
    because the opposite shipped: seed rows picked `user_skill` to fit each
    example's narrative, which put 91% of `Experienced` rows on level 4 and
    left levels 1-3 with no `Experienced` rows at all. The classifier learned
    the dropdown instead of the task and returned level 4 for an experienced
    user changing a light bulb.

    Measured as normalised mutual information between the two columns —
    prose in a README did not prevent this the first time, so it is a build
    failure now. NMI is 0 when skill tells you nothing about the label and 1
    when it tells you everything. The original seed data scored **0.657**;
    after `ml/rebalance_skill.py` it is 0.000.

    Also reports empty cells, because a (skill, level) combination with no
    examples is one the model can only ever guess at.
    """
    errors: list[str] = []
    if not rows:
        return errors

    skills = sorted({e["user_skill"] for e in rows})
    levels = sorted({e["risk_level"] for e in rows})
    n = len(rows)

    def entropy(counts) -> float:
        return -sum((c / n) * math.log(c / n) for c in counts if c)

    joint = Counter((e["user_skill"], e["risk_level"]) for e in rows)
    h_skill = entropy(Counter(e["user_skill"] for e in rows).values())
    h_level = entropy(Counter(e["risk_level"] for e in rows).values())
    h_joint = entropy(joint.values())
    mutual_information = h_skill + h_level - h_joint
    denominator = min(h_skill, h_level)
    nmi = mutual_information / denominator if denominator else 0.0

    empty = [(s, lv) for s in skills for lv in levels if not joint[(s, lv)]]

    print(f"\n  skill/label independence ({label}):")
    print(f"    normalised mutual information: {nmi:.3f}  (0 = independent, target < {NMI_LIMIT})")
    if empty:
        print(f"    {len(empty)} empty (skill, level) cell(s): {empty}")

    if nmi > NMI_LIMIT:
        errors.append(
            f"user_skill predicts risk_level too well in {label}: normalised mutual "
            f"information {nmi:.3f} > {NMI_LIMIT}. risk_level must describe the task, "
            f"not who is asking — see ml/data/README.md, '5 risk levels'."
        )
    return errors


def summarise(name: str, rows: list[dict]) -> None:
    print(f"{len(rows)} examples in {name}")
    print(f"  by category: {dict(sorted(Counter(e['category'] for e in rows).items()))}")
    print(f"  by risk_level: {dict(sorted(Counter(e['risk_level'] for e in rows).items()))}")
    print(
        "  with followups: "
        f"{sum(1 for e in rows if e['followup_questions'])} "
        f"({sum(len(e['followup_questions']) for e in rows)} total questions)"
    )


def main() -> int:
    seeds = json.loads(DATA.read_text(encoding="utf-8"))
    errors = validate(seeds)
    summarise(DATA.name, seeds)

    parents = {e["id"]: e for e in seeds if "id" in e}
    generated: list[dict] = []
    if GENERATED.exists():
        generated = json.loads(GENERATED.read_text(encoding="utf-8"))
        print()
        summarise(GENERATED.name, generated)
        print(f"  by rule: {dict(sorted(Counter(e['generation_rule'] for e in generated).items()))}")
        errors += validate(generated, generated=True, parents=parents)

        # A generated variant must never duplicate a seed's task_text, or the
        # same text would carry two independent labels.
        seed_texts = {e["task_text"] for e in seeds}
        for g in generated:
            if g["task_text"] in seed_texts:
                errors.append(f"{g['task_text'][:60]!r}: generated text duplicates a seed")

        print(f"\nTOTAL: {len(seeds) + len(generated)} "
              f"({len(seeds)} hand-written + {len(generated)} generated)")

    # Checked on the COMBINED corpus, which is what actually gets trained on.
    # Seeds alone could look balanced while paraphrase variants reintroduce
    # the skew, since every variant inherits its parent's skill.
    errors += check_skill_label_independence(seeds + generated, label="seed + generated")

    if errors:
        print(f"\n{len(errors)} RULE VIOLATION(S):")
        for msg in errors:
            print(f"  - {msg}")
        return 1

    print("\nAll rules pass.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
