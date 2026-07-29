"""Phase 2 step 4: standards-conformance audit of the labelled dataset.

WHAT THIS IS: an automated cross-check of every label against minimum risk
levels implied by published safety standards and by srs.md 9's own rule
catalog. Each rule below cites the standard it comes from.

WHAT THIS IS NOT: independent expert review, and NOT an inter-rater
agreement statistic. The dataset labels and these rules were authored in
the same session, so a high conformance rate here demonstrates internal
consistency against an external rubric - it does not demonstrate that a
licensed tradesperson would agree. prd.md 7 records this substitution
(no supervisor/domain expert was available) and it remains flagged as
provisional. See ml/data/REVIEW.md for the honest write-up.

The direction that matters is UNDER-labelling: a task labelled below its
standards-implied floor is a false negative, which is the failure mode
prd.md 7 sets a >=95% recall target against. Over-labelling is reported
separately and is not treated as a defect.

Run: python ml/review_high_risk.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

DATA = Path(__file__).parent / "data"


def has(e: dict, *words: str) -> bool:
    """Whole-word/phrase match against task_text.

    Word-boundary anchored on purpose: a plain substring test matched
    "flood" inside "floodlight" during the first audit run and produced a
    false positive on an unrelated example.
    """
    t = e["task_text"].lower()
    return any(re.search(r"\b" + re.escape(w.strip()) + r"\b", t) for w in words)


def hz(e: dict, *tags: str) -> bool:
    return bool(set(e["hazards"]) & set(tags))


def unanswered(e: dict, field: str) -> bool:
    return any(
        f["field"] == field and f["answer"] is None for f in e["followup_questions"]
    )


# (id, floor, standard reference, predicate)
# Floor = the minimum risk_level the cited standard implies for this situation.
RULES = [
    ("active-gas-emergency", 5,
     "HSE / National Gas Emergency guidance: suspected gas escape or CO "
     "presence is an evacuate-and-call-immediately emergency, never a DIY task",
     lambda e: has(e, "smell gas", "smell of gas", "gas leak", "carbon monoxide",
                   "lazy flame", "hissing")),

    # Narrowed after the first audit run: the original predicate was
    # "electrical_shock AND water_damage" co-occurring, which fired on damp
    # locations (a bathroom outlet with power confirmed off). The cited
    # standard is about water ACTIVELY reaching electrics, so the predicate
    # now requires escaping-water language rather than tag co-occurrence.
    ("water-at-live-electrics", 5,
     "srs.md 9: 'Water leak near an electrical outlet -> Dangerous/Do Not "
     "Attempt; instruct isolating power first'",
     lambda e: hz(e, "electrical_shock")
     and has(e, "dripping onto", "pouring down onto", "water leak",
             "standing water", "burst", "flood")),

    ("exposed-live-conductors", 5,
     "OSHA Focus Four (electrocution) / BS 7671: exposed conductors of "
     "unverified status must be treated as live",
     lambda e: has(e, "live wire", "exposed wires", "sparking")),

    ("fragile-roof-surface", 5,
     "HSE INDG284: falls through fragile surfaces (asbestos cement sheet, "
     "rooflights, perspex) are a leading cause of construction fatalities",
     lambda e: has(e, "fragile", "perspex", "asbestos cement")),

    ("gas-appliance-work", 4,
     "Gas Safety (Installation and Use) Regulations 1998: work on gas "
     "fittings/appliances is restricted to registered engineers",
     lambda e: has(e, "gas") and has(e, "install", "connect", "fit ", "move ",
                                     "service", "flue", "hob", "boiler")),

    ("consumer-unit-or-service-head", 4,
     "BS 7671 / Building Regs Part P: consumer-unit and supply-side work is "
     "notifiable and the service head cannot be isolated by the occupier",
     lambda e: has(e, "consumer unit", "fuse box", "main panel", "electrical panel",
                   "panel bus", "service head", "subpanel", "distribution board")),

    ("asbestos", 4,
     "Control of Asbestos Regulations 2012: disturbing asbestos-containing "
     "materials requires assessment and, for many types, a licensed contractor",
     lambda e: hz(e, "asbestos_exposure")),

    ("unknown-load-bearing", 4,
     "srs.md 9: 'Wall demolition with unknown load-bearing status -> "
     "Professional Required; structural assessment recommended'",
     lambda e: unanswered(e, "load_bearing_confirmed")),

    ("confined-space", 4,
     "Confined Spaces Regulations 1997: entry requires risk assessment, "
     "atmosphere testing and emergency arrangements",
     lambda e: hz(e, "confined_space")),

    # Narrowed after the first audit run: the standard says "height above a
    # safe threshold", but the original predicate fired on any mention of a
    # roof, including a low garden outbuilding reached from a step ladder,
    # which is below any meaningful threshold. Explicitly-low contexts are
    # now excluded.
    ("roof-or-height-work", 3,
     "srs.md 9: 'Roof work or height above safe threshold -> Professional "
     "Recommended or Professional Required' (OSHA Focus Four: falls)",
     lambda e: hz(e, "fall_from_height")
     and has(e, "roof", "two storey", "two-story", "three storey", "steep",
             "scaffold", "extension ladder", "first floor")
     and not has(e, "low ", "single storey", "step ladder", "bungalow",
                 "ground level", "from the garden")),

    ("electrical-work-by-beginner", 3,
     "srs.md 9: 'Electrical wiring task + beginner user -> minimum "
     "Professional Recommended'",
     lambda e: e["category"] == "electrical"
     and e["user_skill"] == "Beginner"
     and hz(e, "electrical_shock")),
]


def audit(rows: list[dict]) -> tuple[list, list, dict]:
    under, over = [], []
    fired = Counter()
    for e in rows:
        floors = [(rid, floor, ref) for rid, floor, ref, pred in RULES if pred(e)]
        for rid, _, _ in floors:
            fired[rid] += 1
        if not floors:
            # No standard implies a floor. Only note it if the label is severe,
            # so we can eyeball whether severity is justified by something the
            # rules do not encode.
            if e["risk_level"] >= 4:
                over.append((e, None, None))
            continue
        rid, floor, ref = max(floors, key=lambda f: f[1])
        if e["risk_level"] < floor:
            under.append((e, floor, rid, ref))
    return under, over, fired


def main() -> int:
    seeds = json.loads((DATA / "seed_examples.json").read_text(encoding="utf-8"))
    gen_path = DATA / "generated_examples.json"
    generated = json.loads(gen_path.read_text(encoding="utf-8")) if gen_path.exists() else []

    total_under = 0
    for name, rows in (("seed_examples.json", seeds), ("generated_examples.json", generated)):
        if not rows:
            continue
        under, over, fired = audit(rows)
        total_under += len(under)
        checked = sum(1 for e in rows if any(p(e) for _, _, _, p in RULES))
        conforming = checked - len(under)
        pct = (conforming / checked * 100) if checked else 100.0

        print(f"=== {name}: {len(rows)} rows")
        print(f"  {checked} matched at least one standards rule")
        print(f"  {conforming}/{checked} meet or exceed their standards floor ({pct:.1f}%)")
        print(f"  {len(under)} BELOW floor (false-negative direction - defects)")
        print(f"  {len(over)} at risk_level >=4 with no rule firing (review for over-labelling)")
        print(f"  rule hit counts: {dict(fired.most_common())}")
        for e, floor, rid, ref in under:
            print(f"    UNDER  [{rid}] needs >={floor}, has {e['risk_level']}: {e['task_text'][:72]}")
            print(f"           standard: {ref[:110]}")
        print()

    if total_under:
        print(f"{total_under} label(s) below their standards floor - fix before splitting.")
        return 1
    print("No labels fall below their standards-implied floor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
