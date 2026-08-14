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

TWO DIRECTIONS, SINCE 2026-08-13.

UNDER-labelling is the direction that matters most: a task below its
standards-implied floor is a false negative, the failure mode prd.md 7 sets a
>=95% recall target against. Each FLOOR rule below cites the standard it
derives from.

OVER-labelling is now also a defect, which it was not before. A floors-only
audit can never show a label is RIGHT, only that it is not too low - and
over-labelling has its own cost: prd.md 6's product principle is that a system
which calls everything dangerous gets ignored, taking its correct warnings down
with it. The CEILING check bounds how far a label may exceed the level its
cited evidence derives.

Requires `basis` on every row: run `python ml/assign_basis.py --apply` first.
Rows without it are counted and skipped rather than silently passing.

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

    # Citation corrected 2026-08-13. This rule previously cited INDG284, which
    # HSE's own fragile-surfaces page does not reference - it appears to be a
    # withdrawn 2008 leaflet. HSG33 (paras 170-202) and GEIS5 are the current
    # guidance. See ml/data/sources.json -> rejected -> indg284.
    ("fragile-roof-surface", 5,
     "HSE HSG33 paras 170-202 and GEIS5: falls through fragile surfaces "
     "(asbestos cement sheet, rooflights, perspex) are a leading cause of "
     "construction fatalities",
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

    # RETIRED 2026-08-13: ("electrical-work-by-beginner", 3, ...)
    #
    # This rule audited a floor the product no longer implements. srs.md 9's
    # "electrical wiring + beginner -> minimum Professional Recommended" was
    # replaced in the shipped catalog by `fixed_wiring_work`, floor 3 FOR
    # EVERYONE, when user_skill was dropped from the product on 2026-08-02
    # (skill_level is deliberately not carried into the Convex schema).
    #
    # It was also the only rule here keyed on user_skill, so when
    # ml/rebalance_skill.py reassigned skill values to break the confound
    # (commit 741fcc9) it began firing on seed-0051 and its generated variant,
    # failing the audit against a label nobody had changed.
    #
    # Keeping it would have meant either re-labelling a correct example or
    # letting a permanently-red gate rot. The dataset label does not need to
    # encode the engine's floors: `fixed_wiring_work` matches "light switch" and
    # "dimmer" and lifts that task to 3 at serve time via max(ML, rules).
    # Gated on isolation NOT being confirmed, which is a deliberate divergence
    # from the shipped catalog. `fixed_wiring_work` has `gatedBy: []` and floors
    # at 3 regardless of what the description claims, because the ENGINE must not
    # lower a risk level on the strength of free text a user typed - it can only
    # escalate (rules.md 4.2).
    #
    # The DATASET is labelling something different: what the task inherently
    # demands given the stated facts. ml/data/README.md documents this as the
    # paired-seed pattern (the four "install a ceiling fan" rows) - isolation
    # confirmed means shock-related PPE drops and the level falls.
    #
    # Both are right for their purpose and max(ML, rules) reconciles them: the
    # served answer for a confirmed-isolated outlet swap is still 3, because the
    # engine floors it there. Auditing the dataset against the ungated catalog
    # floor would force a re-label that contradicts a documented design decision.
    ("fixed-wiring-work", 3,
     "convex/ai/ruleEngine/catalog.ts `fixed_wiring_work` (floor 3, all users): "
     "work on fixed wiring means work on conductors that may be live. Gated here "
     "on isolation not being stated as confirmed - see the comment above",
     lambda e: hz(e, "electrical_shock")
     and has(e, "wiring", "rewire", "circuit", "socket", "outlet", "junction box",
             "consumer unit", "fuse box")
     and not has(e, "lamp", "plug", "extension lead", "appliance")
     and not (has(e, "breaker off", "breaker is off", "switched the breaker off",
                  "switched off the breaker", "power is off", "isolated")
              and has(e, "verified", "confirmed", "dead", "voltage tester",
                      "no voltage", "tested"))),
]


# --- ceilings ---------------------------------------------------------------
# Every rule above defines a FLOOR, so until 2026-08-13 this audit could only
# ever catch under-labelling. That is the direction that matters most
# (prd.md 7's recall target), but a floors-only audit can never show a label is
# RIGHT - only that it is not too low. Over-labelling has a real cost of its
# own: prd.md 6's product principle is that a system which calls everything
# dangerous gets ignored, at which point its correct warnings go unread too.
#
# A ceiling is the MAXIMUM risk level the available evidence supports. A label
# above its ceiling is an over-labelling defect.
#
# EXEMPTIONS ARE NOT LOOPHOLES. Two things legitimately push a row above what
# its hazards alone would justify, both documented product policy rather than
# judgement, so a row carrying either is exempt from ceilings entirely:
#   1. An unanswered safety-critical follow-up -> 5 (ml/data/README.md).
#   2. Active emergency language -> 5 (ml/data/rubric.md).
# Without these, the ~36 seeds sitting at >= 4 via the escalation rule - which
# REVIEW.md's over-labelling review already examined and cleared - would all
# report as false positives and the check would be useless.

# HOW THE CEILING IS DERIVED, AND WHY NOT FROM HAZARD TAGS
# ---------------------------------------------------------
# The first implementation of this section wrote its own hazard predicates
# ("only recoverable hazards -> max 3", "level 5 needs a grave hazard"). It
# produced 24 flags and ALL 24 WERE BUGS IN THE CEILING, not defects in the
# labels: it knew nothing about restrictions, so notifiable plumbing and
# F-gas refrigerant work looked over-labelled; and its list of routes to level 5
# omitted adverse conditions and fragile surfaces.
#
# The lesson is that hazard tags do not carry enough information to bound a
# level - the same conclusion ml/assign_basis.py reached from the other
# direction. So the ceiling is anchored to `basis.rubric_level`, which already
# combines cited severity and cited restriction, rather than to a second,
# inferior copy of that logic living here.
#
# CEILING = rubric_level + CEILING_SLACK.
#
# The slack is what makes this an audit rather than a tautology. Setting it to 0
# would assert the rubric is always right and flag every row where an author
# disagreed by a single band - circular, since the rubric was built by looking
# at these labels. One band of slack says: an author may exceed the derived
# level by one, and anything beyond that needs a recorded reason. It flags the
# tail, which is what an audit is for.
#
# CALIBRATION, measured 2026-08-13 over the 256 seeds:
#     slack 0 -> 31 flagged      slack 1 -> 0 flagged      slack 2 -> 0 flagged
# So the check is live rather than vacuous, and the bound is TIGHT: the largest
# over-label anywhere in the dataset relative to its cited evidence is exactly
# one band. If a future change makes slack 1 start flagging rows, that is a real
# regression and not a threshold to loosen.
CEILING_SLACK = 1

EMERGENCY_LANGUAGE = (
    "smell gas", "smell of gas", "gas leak", "carbon monoxide", "lazy flame",
    "live wire", "live wires", "exposed wires", "sparking", "bulging", "sagging",
    "widening", "spreading", "backing up", "pouring", "burst", "keeps tripping",
    "has come through", "feels bouncy", "dripping onto", "crack is running",
    "crack is appearing", "leaning", "come through",
)


def exempt_from_ceilings(e: dict) -> str | None:
    """Documented policy escalations that legitimately exceed a hazard ceiling."""
    if any(
        f["field"] in ("power_isolated", "load_bearing_confirmed", "gas_line_present")
        and f["answer"] is None
        for f in e["followup_questions"]
    ):
        return "unanswered safety-critical follow-up (README.md escalation rule)"
    if has(e, *EMERGENCY_LANGUAGE):
        return "active emergency language in task_text"
    return None


def ceiling_for(e: dict) -> tuple[int, str] | None:
    """Max level the cited evidence supports, or None if it cannot be derived."""
    basis = e.get("basis")
    if not basis or "rubric_level" not in basis:
        return None  # basis not yet written; run `python ml/assign_basis.py --apply`
    derived = basis["rubric_level"]
    sev = basis["severity"]["band"]
    res = basis["restriction"]["class"]
    return (
        min(5, derived + CEILING_SLACK),
        f"ml/data/rubric.md derives {derived} from {sev}/{res} "
        f"(+{CEILING_SLACK} band of author slack)",
    )


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


def audit_ceilings(rows: list[dict]) -> tuple[list, int, int]:
    """Rows labelled ABOVE the maximum their evidence supports."""
    above, exempted, underivable = [], 0, 0
    for e in rows:
        if exempt_from_ceilings(e):
            exempted += 1
            continue
        cap = ceiling_for(e)
        if cap is None:
            underivable += 1
            continue
        limit, ref = cap
        if e["risk_level"] > limit:
            above.append((e, limit, "above-evidence-ceiling", ref))
    return above, exempted, underivable


def main() -> int:
    seeds = json.loads((DATA / "seed_examples.json").read_text(encoding="utf-8"))
    gen_path = DATA / "generated_examples.json"
    generated = json.loads(gen_path.read_text(encoding="utf-8")) if gen_path.exists() else []

    total_under = 0
    total_above = 0
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

        above, exempted, underivable = audit_ceilings(rows)
        total_above += len(above)
        print(f"  ceilings: {len(above)} ABOVE ceiling (over-labelling direction), "
              f"{exempted} exempt via a documented escalation"
              + (f", {underivable} with no basis written" if underivable else ""))
        for e, cap, cid, ref in above:
            print(f"    ABOVE  [{cid}] allows <={cap}, has {e['risk_level']}: {e['task_text'][:72]}")
            print(f"           basis: {ref[:110]}")
        print()

    if total_under or total_above:
        if total_under:
            print(f"{total_under} label(s) BELOW their standards floor - the recall direction.")
        if total_above:
            print(f"{total_above} label(s) ABOVE their evidence ceiling - the over-labelling direction.")
        print("Fix before splitting.")
        return 1
    print("No labels fall below their standards-implied floor, and none exceeds its ceiling.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
