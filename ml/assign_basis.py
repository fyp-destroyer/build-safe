"""Derive a cited `basis` for every labelled example, per ml/data/rubric.md.

Run: python ml/assign_basis.py            # report only, writes nothing
     python ml/assign_basis.py --apply    # write `basis` into the data files

WHAT THIS WRITES AND WHAT IT REFUSES TO WRITE
---------------------------------------------
It writes `basis` — the severity band, restriction class and source ids behind
a label. It NEVER writes `risk_level`, `risk_label`, `hazards` or `task_text`.

That restraint is deliberate and it is the whole safety argument of this script.
The rubric produces a level; where that disagrees with the hand-authored label,
the correct response is a human deciding which one is wrong, not a script
silently restating 256 safety judgements as its own. Disagreements are printed
as a review queue and the label is left alone. `ml/rebalance_skill.py` made the
same call for the same reason.

WHY SEVERITY NEEDS CONTEXT, NOT JUST THE HAZARD TAG
----------------------------------------------------
Measured before writing this: in seed_examples.json, `cuts_lacerations` spans
risk levels 1-5 and `respiratory_hazard` spans 1-5. The tag records WHICH hazard
is present, not how bad it is - a craft knife and a circular saw are both
`cuts_lacerations`; sanding filler and cutting paving slabs are both
`respiratory_hazard`. So each hazard has a base band plus context predicates
that raise or lower it, and every predicate cites the source that justifies it.

Deriving severity from the tag alone would produce a number that looks sourced
and is not.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

DATA = Path(__file__).parent / "data"
APPLY = "--apply" in sys.argv


def has(text: str, *words: str) -> bool:
    """Whole-word/phrase match. Anchored, per the 'floodlight' false positive
    recorded in REVIEW.md."""
    return any(re.search(r"\b" + re.escape(w.strip()) + r"\b", text) for w in words)


# --- Axis 1: severity -------------------------------------------------------
# (band, source_ids, note). Bands are S1/S2/S3 per rubric.md; severity caps at 3.

POWERED_CUTTING = ("circular saw", "table saw", "angle grinder", "chainsaw",
                   "mitre saw", "miter saw", "reciprocating saw", "jigsaw",
                   "disc cutter", "grinder")
SILICA_WORK = ("concrete", "brick", "block", "paving", "stone", "mortar",
               "masonry", "tile", "tiles", "render", "screed", "chase", "chasing")
LOW_HEIGHT = ("step ladder", "stepladder", "step stool", "ground level",
              "single storey", "single-storey", "bungalow", "from the garden",
              "low wall")
# A stated, specific isolation is a real control and genuinely lowers the worst
# credible outcome — that is the whole point of the paired seeds documented in
# README.md ("install a ceiling fan" x4). Severity must account for it or every
# electrical example collapses to one band. Requires BOTH an isolation claim and
# a verification claim: "I turned the breaker off" alone is unverified.
ISOLATION_CLAIMED = ("breaker is off", "breaker off", "switched off the breaker",
                     "turned off the breaker", "power is off", "isolated at the breaker",
                     "circuit is off", "unplugged")
ISOLATION_VERIFIED = ("verified", "confirmed", "checked it's dead", "checked its dead",
                      "voltage tester", "tested dead", "proven dead", "no voltage")


ROOF_WORK = ("roof", "chimney", "rafter", "truss", "ridge", "flashing", "slate", "tile batten")
FRAGILE = ("fragile", "perspex", "asbestos cement", "rooflight", "skylight")
# Structural alteration is not only DEMOLITION. Inserting a lintel or beam,
# cutting a new opening, widening one, or forming a staircase opening all alter
# load paths and are notifiable under Approved Document A. An earlier draft
# matched removal verbs only, so "install a steel lintel over a widened window"
# and "cut a large opening for bifold doors" scored two bands low.
STRUCTURAL_ALTERATION = ("remove", "removing", "removal", "demolish", "demolition",
                         "take down", "knock through", "knock down", "cut into",
                         "cutting into", "open up", "opening", "lintel", "beam",
                         "rsj", "widen", "widened", "widening", "staircase",
                         "retaining wall", "underpin", "chimney breast")


def severity(e: dict) -> tuple[int, list[str], str]:
    """Worst credible outcome band, adjusted for controllability. (band, sources, why).

    S1-S3 grade the OUTCOME. S4-S5 grade CONTROLLABILITY, which is a separate
    question and the reason an earlier version of this function compressed every
    label toward the middle: it capped at S3, so anything dangerous for physical
    rather than legal reasons could not reach 4-5 and landed at 3. Measured on
    2026-08-12, mean delta against the hand labels ran +1.00 at level 1 down to
    -1.59 at level 5 - monotonic, i.e. structural, not noise.

    S4 is NOT "feels dangerous". It requires a published document specifying
    ENGINEERED CONTROLS or SPECIALIST EQUIPMENT - staging, cable-locating gear,
    enclosure, atmosphere testing, temporary structural support - as opposed to
    care and PPE. That is a factual question about a document, which keeps the
    band citable and stops it becoming a place to put things that merely worry us.
    """
    text = f"{e['task_text']} {' '.join(e.get('tools_available') or [])}".lower()
    hazards = set(e["hazards"])

    best = (1, ["cpsc-neiss"], "no hazard tagged; worst credible outcome is self-treating")
    # A hazard tag records that a hazard EXISTS, not that it is significant.
    # "fill and sand small nail holes" carries respiratory_hazard and
    # "seal the grout lines" carries chemical_exposure, but neither reaches
    # "needs medical attention". Without this, every trivial task with any tag
    # floored at 2 and the whole level-1 band collapsed.
    trivial = has(text, "small", "minor", "single", "a few", "touch up", "hairline",
                  "offcuts", "nail holes", "splashback") and not has(text, *POWERED_CUTTING)

    def bid(band: int, srcs: list[str], why: str) -> None:
        nonlocal best
        if trivial and band == 2:
            return  # magnitude too small for the S2 threshold; stays S1
        if band > best[0]:
            best = (band, srcs, why)

    # Severity otherwise models injury to the PERSON DOING THE WORK. Some tasks
    # are trivially safe to perform and fail later onto somebody else: a TV or a
    # loaded shelf coming off a plasterboard wall, a stair gate that does not
    # hold. Those carry `hazards: []` and scored 1 against a hand label of 2.
    #
    # This is a deliberate, narrow extension rather than a new axis: it lifts
    # S1 -> S2 only, and only for a suspended-load-over-people pattern. The
    # citation is the manual-handling ACOP's treatment of load and fixing
    # failure; it is the weakest evidence in the rubric and is marked as such.
    if has(text, "mount", "mounting", "hang", "hanging", "fix", "fixing", "fit", "put up") \
            and has(text, "tv", "television", "shelf", "shelves", "cabinet", "mirror",
                    "radiator", "stair gate", "bracket", "heavy"):
        bid_third_party = True
    else:
        bid_third_party = False

    if hazards and hazards != {"none"}:
        # S3 hazards - death or permanent impairment credible.
        if "electrical_shock" in hazards:
            if has(text, *ISOLATION_CLAIMED) and has(text, *ISOLATION_VERIFIED):
                bid(2, ["cpsc-neiss-electrical"],
                    "electric shock, but supply stated isolated AND verified dead; "
                    "residual risk is contact with a mis-identified circuit")
            else:
                bid(3, ["cpsc-neiss-electrical"],
                    "electric shock on an unverified circuit; DIY-specific severity evidence")
        if "structural_collapse" in hazards:
            bid(3, ["hse-fatal-injuries"], "structural failure; crush injury credible")
        if "gas_leak" in hazards:
            bid(3, ["gas-safety-regs-1998"], "gas escape; explosion and CO poisoning credible")
        if "fire" in hazards:
            bid(3, ["hse-fatal-injuries"], "ignition; burn injury and property fire credible")
        if "buried_utility_strike" in hazards:
            bid(3, ["hsg47"], "buried services cannot be identified as live by sight (HSG47)")
        if "asbestos_exposure" in hazards:
            bid(3, ["car-2012"], "asbestos fibre release; long-latency fatal disease")
        if "confined_space" in hazards:
            bid(3, ["confined-spaces-regs-1997"], "confined space; asphyxiation credible")

        if "fall_from_height" in hazards:
            # LOW_HEIGHT must not apply to work ON a roof. A single-storey
            # bungalow roof is still a roof: HSG33 governs it, the working
            # position is a pitched surface, and "replace a cracked ridge tile
            # on a single storey bungalow" was scoring 2 against a hand label
            # of 3 purely because "single storey" appeared in the text.
            if has(text, *LOW_HEIGHT) and not has(text, *ROOF_WORK):
                bid(2, ["cpsc-neiss"], "fall from an explicitly low working position")
            else:
                bid(3, ["hse-fatal-injuries"],
                    "fall from height; 31 of 126 GB worker deaths 2025/26, the most common cause")

        # S2 base hazards, raised by context.
        if "cuts_lacerations" in hazards:
            if has(text, *POWERED_CUTTING):
                bid(3, ["cpsc-power-tools-2003h054"],
                    "powered cutting tool; amputation and major laceration credible")
            else:
                bid(2, ["cpsc-neiss"], "hand-tool laceration; medical attention, full recovery")
        if "respiratory_hazard" in hazards:
            if has(text, *SILICA_WORK):
                bid(3, ["osha-silica-1926-1153"],
                    "respirable crystalline silica from cutting/grinding masonry (29 CFR 1926.1153)")
            else:
                bid(2, ["cpsc-neiss"], "nuisance dust or fume; irritation, full recovery")
        if "chemical_exposure" in hazards:
            bid(2, ["cpsc-neiss"], "chemical splash or fume; medical attention, full recovery")
        if "burns" in hazards:
            bid(2, ["cpsc-neiss"], "thermal burn; medical attention, full recovery")
        if "heavy_object_handling" in hazards:
            bid(2, ["manual-handling-regs-1992"],
                "load above the L23 guideline filter figures; musculoskeletal injury")
        if "hearing_damage" in hazards:
            # Never above S2: noise causes impairment, not death.
            bid(2, ["noise-regs-2005"],
                "sustained exposure above the 85 dB(A) upper action value")
        if "water_damage" in hazards:
            bid(2, ["cpsc-neiss"], "escaping water; property damage and slip injury")

        # --- S4: published guidance specifies engineered controls ------------
        if "fall_from_height" in hazards and has(text, *FRAGILE):
            bid(4, ["hsg33", "geis5"],
                "fragile surface: HSG33 paras 170-202 require staging or covers, not care alone")
        if "fall_from_height" in hazards and has(text, *ROOF_WORK) and not has(text, *LOW_HEIGHT):
            bid(4, ["hsg33"],
                "roof work: HSG33 specifies edge protection, staging or harness as the control")
        if "buried_utility_strike" in hazards:
            bid(4, ["hsg47"],
                "HSG47 requires cable-locating equipment; a service is located only once safely exposed")
        if "asbestos_exposure" in hazards:
            bid(4, ["car-2012"],
                "CAR 2012 requires controlled conditions; many categories require a licensed contractor")
        if "confined_space" in hazards:
            bid(4, ["confined-spaces-regs-1997"],
                "atmosphere testing and rescue arrangements required BEFORE entry")
        if "structural_collapse" in hazards and has(text, *STRUCTURAL_ALTERATION):
            bid(4, ["approved-document-a"],
                "structural alteration requires engineered temporary support and building control sign-off")
        if "gas_leak" in hazards:
            bid(4, ["gas-safety-regs-1998"],
                "gas fittings require registered-engineer competence and test equipment")
        # Lead paint: HSE specifies on-tool extraction, wet abrasive methods and
        # APF-20 RPE, and forbids blow lamps / >500 C hot air. Engineered
        # controls, so S4 rather than plain chemical_exposure at S2.
        if has(text, "lead paint", "leaded paint", "lead-based paint") or (
            has(text, "strip", "stripping", "sand", "sanding", "burn off")
            and has(text, "victorian", "edwardian", "georgian", "1930s", "1950s",
                    "1960s", "1970s", "period property", "listed")
            and has(text, "paint")
        ):
            bid(4, ["lead-at-work-regs-2002"],
                "lead paint: HSE requires on-tool extraction, wet methods and APF-20 RPE")
        # Solvent spraying in an enclosed or unventilated space concentrates
        # vapour to a flammable/toxic level that ordinary ventilation does not
        # control - the hazard is the enclosure, not the product.
        if hazards & {"chemical_exposure", "respiratory_hazard"} and (
            has(text, "spray", "spraying", "solvent", "epoxy", "two pack", "2 pack")
            and has(text, "sealed", "closed", "unventilated", "no ventilation",
                    "basement", "cellar", "enclosed", "airless")
        ):
            bid(4, ["coshh-2002"],
                "solvent spraying in an enclosed space: COSHH reg. 7 puts ventilation "
                "and engineering controls above PPE, and solvents always need ventilation")
        # Burning treated or painted timber releases arsenic, copper and lead
        # fume. REVIEW.md already flagged this in its over-labelling review as a
        # hazard the standards rules did not encode; now it does.
        if has(text, "burn", "burning", "bonfire") and has(
            text, "treated timber", "treated wood", "painted", "tanalised",
            "pressure treated", "offcuts", "old timber"
        ):
            bid(4, ["coshh-2002", "lead-at-work-regs-2002"],
                "burning treated or painted timber releases arsenic, copper and lead fume")

    if bid_third_party and best[0] == 1:
        best = (2, ["manual-handling-regs-1992"],
                "trivial to perform, but a fixing failure drops a load onto whoever is "
                "below afterwards - consequence falls on a third party, not the doer")

    return best


# --- Axis 2: restriction ----------------------------------------------------
# Ordered most severe first; the first match wins.

SERIOUS_HAZARDS = {"electrical_shock", "structural_collapse", "gas_leak", "fire",
                   "buried_utility_strike", "asbestos_exposure", "confined_space"}

# A task_text describing something ALREADY GOING WRONG rather than an action the
# user intends to take. Same test make_splits.py stratifies on, where it is
# documented as "almost entirely risk 5 ... the highest-stakes inputs the system
# will ever receive".
PROBLEM_REPORT = re.compile(r"^(there|the |my |a |water |sewage |i can )", re.I)
ACTIVE_FAULT = ("keeps tripping", "backing up", "burst", "pouring", "dripping onto",
                "leaking", "has come through", "feels bouncy", "is appearing",
                "is running", "is spreading", "is widening", "is bulging", "is sagging",
                "is moving", "smell", "sparking", "buzzing", "hissing", "scorch",
                "burning smell", "will not stop", "won't stop")

RESTRICTIONS = [
    ("R3", 5, ["gas-safety-regs-1998"], "active gas emergency - evacuate and call, never a DIY task",
     lambda t, h: has(t, "smell gas", "smell of gas", "gas leak", "carbon monoxide",
                      "lazy flame", "hissing")),
    ("R3", 5, ["cpsc-neiss-electrical"], "exposed conductors of unverified status - treat as live",
     lambda t, h: has(t, "live wire", "live wires", "exposed wires", "sparking")),
    # The general emergency case. An active fault is a cease-and-report
    # situation, not a task to be graded on competence: the correct advice is
    # the same for a beginner and a professional, which README.md gives as the
    # defining property of level 5. Narrow predicates missed "my breaker keeps
    # tripping", "water is dripping onto the fuse box", "sewage is backing up",
    # "the floor feels bouncy and a crack is appearing" - all hand-labelled 5.
    ("R3", 5, ["hse-fatal-injuries"],
     "active fault already occurring alongside a serious hazard - stop, leave, get help",
     lambda t, h: bool(PROBLEM_REPORT.match(t)) and has(t, *ACTIVE_FAULT)
                  and bool(h & SERIOUS_HAZARDS)),
    # Sewage backflow is a biohazard emergency but tags respiratory/chemical
    # rather than anything in SERIOUS_HAZARDS, so it needs its own predicate.
    ("R3", 5, ["hse-fatal-injuries"],
     "sewage backflow into living space - biohazard, not a DIY clean-up",
     lambda t, h: has(t, "sewage", "foul water", "soil water")
                  and has(t, "backing up", "backflow", "coming up", "overflowing")),
    # Level 5 means "nobody does this RIGHT NOW" (README.md), and adverse
    # conditions are exactly that: the task may be a 3 or 4 in the dry, and is
    # a 5 while the surface is wet, icy or being rained on. Without this,
    # "go up on a wet, steep roof during the rain" scored the same as the same
    # roof in good weather.
    ("R3", 5, ["hsg33"],
     "working at height in adverse conditions - defer until the surface is safe",
     lambda t, h: "fall_from_height" in h
                  and has(t, "wet", "icy", "ice", "raining", "in the rain", "storm",
                          "windy", "gale", "slippery", "frost", "frosty")),
    # Fragile surfaces are never a "right now" task: HSG33/GEIS5 treat walking
    # on them as the failure mode itself, not a controllable risk.
    ("R3", 5, ["hsg33", "geis5"],
     "walking on a fragile surface - the control is not to, at any skill level",
     lambda t, h: "fall_from_height" in h
                  and has(t, "walk across", "walk on", "stand on", "get on")
                  and has(t, *FRAGILE)),

    ("R2", 4, ["car-2012"],
     "asbestos: removal, repair or disturbance is regulated; many categories need a licensed contractor",
     lambda t, h: "asbestos_exposure" in h),
    ("R2", 4, ["gas-safety-regs-1998"],
     "work on gas fittings/appliances is restricted to registered engineers",
     lambda t, h: has(t, "gas") and has(t, "install", "connect", "fit", "move",
                                        "service", "flue", "hob", "boiler")),
    ("R2", 4, ["confined-spaces-regs-1997"],
     "confined space: entry requires a safe system of work and emergency arrangements in place first",
     lambda t, h: "confined_space" in h),
    # F gas applies to work on the SEALED REFRIGERANT CIRCUIT, not to any task
    # near an air conditioner. Matching the appliance name alone made "clean the
    # filter on a portable air conditioning unit" a level 4 - an absurd
    # over-label, and the more damaging direction for a product whose stated
    # principle (prd.md 6) is that crying wolf gets it ignored.
    ("R2", 4, ["fgas-qualifications"],
     "F gas: it is against the law to work on equipment containing fluorinated gases unqualified",
     lambda t, h: has(t, "refrigerant", "regas", "recharge", "recover", "pipework",
                      "install", "installing", "commission", "decommission")
                  and has(t, "refrigerant", "air conditioning", "air con", "heat pump",
                          "split system")),
    # Likewise G3 governs INSTALLING or altering an unvented system, not routine
    # user operations on one. Topping up pressure via the filling loop is a task
    # the manufacturer documents for the householder.
    ("R2", 4, ["approved-document-g"],
     "Part G3: an unvented/sealed hot water system may only be installed by a competent person",
     lambda t, h: has(t, "unvented", "sealed system", "pressure relief", "expansion vessel",
                      "hot water cylinder")
                  and not has(t, "top up", "topping up", "filling loop", "bleed", "bleeding",
                              "reset", "thermostat setting")),
    ("R2", 4, ["approved-document-a"],
     "structural alteration: notifiable building work requiring design and building control sign-off",
     lambda t, h: "structural_collapse" in h and has(t, *STRUCTURAL_ALTERATION)),

    # R2h has been retired: "specialist controls are required" is a statement
    # about CONTROLLABILITY, not about law, so it belongs on the severity axis
    # (band S4) where it now lives. Keeping it here made the restriction axis
    # carry two unrelated meanings and hid the compression bug.

    # Part P notifiable work floors at 4, not 3. A householder may do it, but it
    # must be certified by a REGISTERED COMPETENT PERSON or notified to building
    # control - so completing it lawfully requires a qualified professional in
    # the loop, which is README.md's definition of level 4. Level 3 is the band
    # below: fixed-wiring work that is not notifiable (see the next entry), which
    # is also where convex/ai/ruleEngine/catalog.ts puts `fixed_wiring_work`.
    #
    # `excludes` matters as much as the keywords: rewiring a table LAMP or a plug
    # is appliance repair, not fixed wiring, and is not notifiable.
    ("R1", 4, ["approved-document-p"],
     "notifiable electrical work: householder may do it, but it must be inspected and certified",
     lambda t, h: has(t, "consumer unit", "fuse box", "main panel", "electrical panel",
                      "service head", "subpanel", "distribution board", "rewire", "rewiring",
                      "new circuit", "dedicated circuit", "ring main", "ev charging",
                      "ev charger", "charging point")
                  and not has(t, "lamp", "plug", "extension lead", "appliance", "cord")),
    # Part P also makes location notifiable: new electrical work in a kitchen,
    # bathroom, or outdoors, regardless of whether a new circuit is involved.
    ("R1", 4, ["approved-document-p"],
     "notifiable by location: new electrical work in a kitchen, bathroom or outdoors",
     lambda t, h: "electrical_shock" in h
                  and has(t, "new", "add", "adding", "install", "installing", "fit", "run")
                  and has(t, "kitchen", "bathroom", "outdoor", "outdoors", "outside",
                          "garden", "garage", "shed", "exterior")
                  and not has(t, "lamp", "plug", "extension lead", "appliance", "cord")),
    # Water Supply (Water Fittings) Regulations 1999 reg. 5: installing certain
    # fittings requires NOTIFYING the water undertaker and not commencing without
    # consent. Altering the supply or drainage layout engages it; swapping a tap
    # washer or a plastic TRV head does not.
    # Water Fittings reg. 5 floors at 3, NOT 4, and the difference is what the
    # restriction actually demands. Part P requires certification by a REGISTERED
    # COMPETENT PERSON - a professional must be in the loop, which is level 4.
    # Reg. 5 requires notifying the water undertaker and awaiting consent, which
    # a householder can do themselves. Same class of duty, different floor.
    #
    # It also applies to ALTERING THE SYSTEM, not to swapping a component on
    # existing pipework: replacing a leaking trap, a flexible hose, a fill valve
    # or a mixer tap is maintenance, and including "replace" here pushed a batch
    # of level-2 tasks to 4.
    ("R1w", 3, ["water-fittings-regs-1999"],
     "notifiable water fittings work: the undertaker must be notified and consent given",
     lambda t, h: "water_damage" in h
                  and has(t, "install", "installing", "reroute", "rerouting", "move",
                          "moving", "extend", "extending", "add", "adding")
                  and has(t, "toilet", "soil stack", "waste", "bathroom suite",
                          "pipework", "piping", "shutoff", "stopcock", "mains",
                          "cylinder", "wet room", "sink", "shower")
                  and not has(t, "washer", "trv head", "plastic head", "cover plate",
                              "hose", "trap", "fill valve", "cartridge", "tap")),
    # Non-notifiable fixed wiring: like-for-like replacement of an accessory on
    # an existing circuit. Not notifiable under Part P, but still work on
    # conductors that may be live - floor 3, matching `fixed_wiring_work` in the
    # shipped catalog.
    ("Rw", 3, ["approved-document-p", "cpsc-neiss-electrical"],
     "fixed-wiring work on an existing circuit; not notifiable, but conductors may be live",
     lambda t, h: "electrical_shock" in h
                  and has(t, "socket", "outlet", "switch", "dimmer", "light fitting",
                          "light fixture", "junction box", "thermostat", "ceiling fan",
                          "wiring", "circuit")
                  and not has(t, "lamp", "plug", "extension lead", "appliance", "cord")),
    ("R1", 3, ["approved-document-p"],
     "structural alteration is notifiable building work requiring assessment and sign-off",
     lambda t, h: "structural_collapse" in h
                  and has(t, "remove", "removing", "demolish", "take down", "knock through")),
]


def restriction(e: dict) -> tuple[str, int, list[str], str]:
    text = e["task_text"].lower()
    hazards = set(e["hazards"])
    for cls, floor, srcs, why, pred in RESTRICTIONS:
        if pred(text, hazards):
            return cls, floor, srcs, why
    return "R0", 0, [], "no restriction identified"


def unanswered_safety_critical(e: dict) -> bool:
    return any(
        f["field"] in ("power_isolated", "load_bearing_confirmed", "gas_line_present")
        and f["answer"] is None
        for f in e["followup_questions"]
    )


def basis_for(e: dict) -> dict:
    s_band, s_srcs, s_why = severity(e)
    r_cls, r_floor, r_srcs, r_why = restriction(e)

    level = max(s_band, r_floor)
    override = None
    if unanswered_safety_critical(e):
        level = 5
        override = "unanswered-safety-critical-followup"

    return {
        "severity": {"band": f"S{s_band}", "implies": s_band,
                     "sources": s_srcs, "rationale": s_why},
        "restriction": {"class": r_cls, "implies": r_floor,
                        "sources": r_srcs, "rationale": r_why},
        "override": override,
        "rubric_level": level,
    }


def main() -> int:
    sources = json.loads((DATA / "sources.json").read_text(encoding="utf-8"))
    known = {s["id"] for s in sources["sources"]}
    unverified = {s["id"] for s in sources["sources"] if not s.get("verified")}

    files = ["seed_examples.json", "generated_examples.json"]
    agree = Counter()
    queue: list[tuple] = []
    cited: Counter = Counter()

    for name in files:
        rows = json.loads((DATA / name).read_text(encoding="utf-8"))
        for e in rows:
            b = basis_for(e)
            e["basis"] = b
            for sid in b["severity"]["sources"] + b["restriction"]["sources"]:
                cited[sid] += 1
                if sid not in known:
                    print(f"  !! {e['id']} cites unknown source id {sid!r}")
            if b["rubric_level"] == e["risk_level"]:
                agree[name] += 1
            else:
                queue.append((name, e, b))

        if APPLY:
            (DATA / name).write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

    total = sum(agree.values()) + len(queue)
    print("=" * 74)
    print("BASIS ASSIGNMENT (ml/data/rubric.md)")
    print("=" * 74)
    for name in files:
        print(f"  {name:26s} {agree[name]:4d} agree with the hand label")
    print(f"  {'REVIEW QUEUE':26s} {len(queue):4d} disagree ({len(queue)/total:.1%} of {total})")

    print("\n  citations used:")
    for sid, n in cited.most_common():
        flag = "  [UNVERIFIED - do not ship]" if sid in unverified else ""
        print(f"    {sid:32s} {n:4d}{flag}")

    if queue:
        print(f"\n  REVIEW QUEUE - rubric vs hand label. Neither is automatically right.")
        by_delta = Counter((b["rubric_level"] - e["risk_level"]) for _, e, b in queue)
        print(f"  deltas (rubric - hand): {dict(sorted(by_delta.items()))}")
        print(f"  {'':4s}{'id':12s} {'hand':4s} {'rub':4s}  basis")
        for name, e, b in queue[:25]:
            print(f"    {e['id']:12s} {e['risk_level']:^4d} {b['rubric_level']:^4d}  "
                  f"{b['severity']['band']}/{b['restriction']['class']}"
                  f"{'/OVERRIDE' if b['override'] else ''}  {e['task_text'][:44]}")
        if len(queue) > 25:
            print(f"    ... and {len(queue) - 25} more")

    if APPLY:
        print(f"\n  Wrote `basis` into {', '.join(files)}. No safety label was changed.")
    else:
        print("\n  Report only - nothing written. Re-run with --apply to write `basis`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
