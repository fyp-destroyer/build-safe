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
import sys
from collections import Counter
from pathlib import Path

DATA = Path(__file__).parent / "data" / "seed_examples.json"

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

REQUIRED_KEYS = {
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
}


def validate(examples: list[dict]) -> list[str]:
    errors: list[str] = []

    def err(example: dict, msg: str) -> None:
        errors.append(f"{example.get('task_text', '<no task_text>')[:60]!r}: {msg}")

    seen_texts: set[str] = set()

    for e in examples:
        missing = REQUIRED_KEYS - set(e)
        extra = set(e) - REQUIRED_KEYS
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

        # Rule: a tool_available followup only makes sense when tools are
        # genuinely unknown.
        has_tool_followup = any(
            f.get("field", "").startswith("tool_available:") for f in e["followup_questions"]
        )
        if has_tool_followup and e["tools_available"]:
            err(e, "tool_available followup present but tools_available is non-empty")

    return errors


def main() -> int:
    examples = json.loads(DATA.read_text(encoding="utf-8"))
    errors = validate(examples)

    print(f"{len(examples)} examples in {DATA.name}")
    print(f"  by category: {dict(sorted(Counter(e['category'] for e in examples).items()))}")
    print(f"  by risk_level: {dict(sorted(Counter(e['risk_level'] for e in examples).items()))}")
    print(
        "  with followups: "
        f"{sum(1 for e in examples if e['followup_questions'])} "
        f"({sum(len(e['followup_questions']) for e in examples)} total questions)"
    )

    if errors:
        print(f"\n{len(errors)} RULE VIOLATION(S):")
        for msg in errors:
            print(f"  - {msg}")
        return 1

    print("\nAll rules pass.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
