"""The hardcoded safety rule catalog (Phase 5).

This module is DATA, not logic. It is the single source of truth for which
hazards exist, what each one escalates risk to, and how each is explained to
a user. `rules.py` evaluates it; nothing else may define a hazard.

NON-NEGOTIABLE CONSTRAINTS (rules.md §4, CLAUDE.md):

  * This catalog is hardcoded and version-controlled. There is deliberately
    no `safety_rules` table, no admin UI, and no runtime edit path - changing
    a rule means a code change and a code review (srs.md §2.5, §9).
  * Every rule can only ever RAISE risk to its `floor`. No rule may lower a
    risk level. Callers combine via final_risk = max(ML, rules).
  * The LLM may only ever SELECT rule ids from this set (hazard tagging). It
    cannot invent a rule, cannot assign a risk number, and cannot change a
    floor. Any id it returns that is not a key of RULES is discarded.

JURISDICTION: rules are written in terms of hazard and consequence, not
citations to any specific regulation. Thresholds like "gas work requires a
professional" are near-universal, but the exact licensing regime differs by
country, and this project does not target one - so no rule claims legal
authority it cannot back (see ml/data/REVIEW.md for the same reasoning
applied to dataset labelling).
"""

from __future__ import annotations

from dataclasses import dataclass, field

MIN_RISK_LEVEL = 1
MAX_RISK_LEVEL = 5


@dataclass(frozen=True)
class Rule:
    """One hazard rule.

    `floor` is the minimum risk level a job matching this rule may receive.
    It is a floor, never a ceiling and never an assignment: the engine takes
    the maximum across triggered rules, and the caller takes the maximum of
    that and the ML prediction.
    """

    id: str
    hazard: str
    floor: int
    summary: str
    explanation: str
    keywords: tuple[str, ...] = ()
    # Negative keywords: presence of any of these means the rule does NOT
    # fire, used where a phrase is otherwise ambiguous.
    excludes: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    # If set, the rule only fires for these user_skill values. Lets the
    # catalog express srs.md 9's "electrical wiring task + beginner user"
    # faithfully instead of approximating it by category.
    requires_skill: tuple[str, ...] = ()
    # Follow-up fields whose CONFIRMED-SAFE answer (True) means this hazard
    # does not apply to this job at all, so the rule never fires.
    #
    # This is NOT de-escalation and does not weaken rules.md §4.2. A gate
    # refines the *trigger condition* - it is `excludes` sourced from a user
    # answer instead of from the description text - and nothing anywhere
    # lowers a risk level that was already assigned. The safety property that
    # makes it sound is the default: an UNANSWERED gate still fires the rule,
    # so the worst plausible case holds until the user rules it out. Silence
    # never buys a lower risk level; only an explicit answer does.
    #
    # Only ever gate on a fact the user is genuinely authoritative about
    # ("can you reach this from the floor?"). Never gate a hazard whose
    # presence the user cannot reliably self-assess - see HARD_GATE_RULE_IDS.
    gated_by: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not MIN_RISK_LEVEL <= self.floor <= MAX_RISK_LEVEL:
            raise ValueError(f"rule {self.id}: floor {self.floor} out of range")


def _r(**kw) -> Rule:
    return Rule(**kw)


# ---------------------------------------------------------------------------
# The catalog. Ordered roughly by hazard family for readability; order has no
# effect on evaluation (all matching rules are collected, highest floor wins).
# ---------------------------------------------------------------------------
_RULES: tuple[Rule, ...] = (
    # ---- gas -------------------------------------------------------------
    _r(
        id="active_gas_or_co",
        hazard="gas_leak",
        floor=5,
        summary="Suspected gas escape or carbon monoxide",
        explanation=(
            "A suspected gas escape or carbon monoxide presence is an "
            "emergency, not a task. Leave the area, avoid switches and "
            "naked flames, and contact your gas emergency service."
        ),
        keywords=(
            "smell gas",
            "smell of gas",
            "gas leak",
            "leaking gas",
            "carbon monoxide",
            "co alarm",
            "lazy flame",
            "yellow flame",
            "hissing gas",
            "gas is hissing",
        ),
    ),
    _r(
        id="gas_appliance_work",
        hazard="gas_leak",
        floor=4,
        summary="Work on gas pipework or a gas appliance",
        explanation=(
            "Work on gas pipework, connections or appliances carries a "
            "risk of explosion and poisoning, and in most places is "
            "restricted to registered professionals."
        ),
        keywords=(
            "gas hob",
            "gas boiler",
            "gas furnace",
            "gas fire",
            "gas supply",
            "gas pipe",
            "gas meter",
            "gas appliance",
            "gas cooker",
            "gas water heater",
            "flue",
        ),
    ),
    # ---- electrical ------------------------------------------------------
    _r(
        id="water_at_live_electrics",
        hazard="electrical_shock",
        floor=5,
        summary="Water reaching live electrical equipment",
        explanation=(
            "Water in contact with live electrical equipment is an "
            "electrocution and fire risk. Do not touch anything in the "
            "area; isolate the supply from a safe location if you can, "
            "and get a professional out."
        ),
        keywords=(
            "water is dripping onto",
            "dripping onto the fuse",
            "pouring down onto the light",
            "water near the fuse",
            "water leak near",
            "standing water",
            "flooded",
        ),
    ),
    _r(
        id="exposed_live_conductor",
        hazard="electrical_shock",
        floor=5,
        summary="Exposed conductors of unverified status",
        explanation=(
            "Exposed wiring must be treated as live until proven "
            "otherwise with a tester. Contact can be fatal."
        ),
        keywords=(
            "live wire",
            "exposed wire",
            "bare wire",
            "sparking",
            "arcing",
            "burning smell from the panel",
        ),
    ),
    _r(
        id="supply_side_electrical",
        hazard="electrical_shock",
        floor=4,
        summary="Consumer unit, main panel or supply-side work",
        explanation=(
            "The incoming supply and main board stay live even with "
            "the main switch off, so they cannot be made safe by the "
            "occupier. This is professional work."
        ),
        keywords=(
            "consumer unit",
            "fuse box",
            "main panel",
            "electrical panel",
            "distribution board",
            "subpanel",
            "sub panel",
            "service head",
            "meter tail",
            "main breaker",
            "panel bus",
        ),
    ),
    # Deliberately NOT category-gated. Wiring work turns up inside jobs
    # categorised as tiling (chasing a wall), hvac (thermostats) and general;
    # gating this on category would silently drop the power-isolation
    # question for exactly those cases.
    _r(
        id="fixed_wiring_work",
        hazard="electrical_shock",
        floor=2,
        summary="Work on fixed wiring or accessories",
        explanation=(
            "Working on fixed wiring means working on circuits that "
            "may be live. The supply must be isolated and proven dead "
            "before anything is disturbed."
        ),
        keywords=(
            "wiring",
            "rewire",
            "rewiring",
            "circuit",
            "socket",
            "outlet",
            "light fitting",
            "light fixture",
            "junction box",
            "thermostat",
            "light switch",
            "dimmer",
            "chase a channel",
        ),
    ),
    _r(
        id="electrical_work_by_beginner",
        hazard="electrical_shock",
        floor=3,
        summary="Fixed-wiring work attempted by a beginner",
        explanation=(
            "Working on fixed wiring without experience risks shock "
            "and fire, and faults are often invisible until they "
            "matter. Have the work checked by a qualified electrician."
        ),
        keywords=(
            "wiring",
            "rewire",
            "rewiring",
            "circuit",
            "socket",
            "outlet",
            "light fitting",
            "light fixture",
            "junction box",
            "thermostat",
            "light switch",
            "dimmer",
            "chase a channel",
        ),
        requires_skill=("beginner",),
    ),
    # ---- structural ------------------------------------------------------
    _r(
        id="structural_distress",
        hazard="structural_collapse",
        floor=5,
        summary="Signs of active structural failure",
        explanation=(
            "Spreading cracks, sagging or a floor that moves under "
            "load can indicate a structure that is already failing. "
            "Stop using the area and get a structural engineer to "
            "inspect it before any work is attempted."
        ),
        keywords=(
            "crack is getting wider",
            "keeps getting wider",
            "widening crack",
            "bulging",
            "leaning towards",
            "sagging",
            "feels bouncy",
            "came through the roof",
            "daylight through the ceiling",
        ),
    ),
    _r(
        id="structural_alteration",
        hazard="structural_collapse",
        floor=4,
        summary="Removing or altering a wall or structural element",
        explanation=(
            "Removing a wall or structural member can transfer loads in "
            "ways that are not obvious. A structural engineer must "
            "confirm what is load-bearing and specify any support."
        ),
        keywords=(
            "remove a wall",
            "removing a wall",
            "knock through",
            "take down the wall",
            "take down the stud wall",
            "demolish",
            "remove a load-bearing",
            "chimney breast",
            "load-bearing",
            "load bearing",
            "underpin",
            "steel lintel",
        ),
    ),
    # ---- height / roof ---------------------------------------------------
    _r(
        id="fragile_surface",
        hazard="fall_from_height",
        floor=5,
        summary="Working on a fragile roof surface",
        explanation=(
            "Fragile surfaces such as rooflights, perspex panels and "
            "cement sheeting will not carry a person's weight and are "
            "a leading cause of fatal falls. Do not walk on them."
        ),
        keywords=("fragile", "perspex", "asbestos cement", "rooflight", "corrugated sheet"),
    ),
    _r(
        id="work_at_height",
        hazard="fall_from_height",
        floor=3,
        summary="Work at height on a roof or upper storey",
        explanation=(
            "Falls from height are among the most common causes of "
            "serious injury in construction. Roof and upper-storey "
            "work needs proper access equipment and fall protection."
        ),
        keywords=(
            "roof",
            "two storey",
            "two-story",
            "two story",
            "three storey",
            "upper floor",
            "first floor",
            "scaffold",
            "extension ladder",
            "steep",
        ),
        excludes=(
            "single storey",
            "bungalow",
            "step ladder",
            "ground level",
            "from the garden",
            "low flat",
            "outbuilding",
            "binoculars",
        ),
    ),
    # Split out of `work_at_height` on 2026-08-01. That rule's keywords are
    # unambiguous ("roof", "two storey", "scaffold") and it stays ungated -
    # asking "can you reach the roof from the floor?" is a nonsense question.
    #
    # This rule covers the case that actually broke: work that is plainly
    # overhead but whose HEIGHT THE USER NEVER STATED. "How do I change my
    # light bulb" was tagged `work_at_height` and came back level 3, because
    # the tagger had nowhere to put "I don't know how high this is" except
    # the tag itself. Now that uncertainty becomes a QUESTION: the rule fires
    # while `height_access` is unanswered (worst plausible case), and a user
    # who confirms the work is reachable from floor level closes the gate.
    #
    # No keywords by design - nothing in a description reliably signals
    # "overhead but unstated height", so this is LLM-tag-only. That is safe
    # because it is gated: the worst an over-eager tag can do is cause one
    # extra question to be asked.
    _r(
        id="overhead_work_unknown_height",
        hazard="fall_from_height",
        floor=3,
        summary="Overhead work whose working height has not been established",
        explanation=(
            "Overhead work needs stable, appropriate access equipment. "
            "Standing on a chair, a worktop or the top step of a ladder "
            "is a common cause of falls. Work from a stable platform you "
            "can reach comfortably without stretching."
        ),
        keywords=(),
        gated_by=("height_access",),
    ),
    # Added after measuring which genuinely-dangerous tasks the engine was
    # still missing (ml/analyze_recall.py). Keywords are deliberately
    # multi-word: rules are the cheapest recall this system has precisely
    # because they almost never false-fire, and loose single words would
    # spend that advantage.
    _r(
        id="unprotected_or_adverse_height_work",
        hazard="fall_from_height",
        floor=5,
        summary="Height work in adverse conditions or without fall protection",
        explanation=(
            "A wet, icy or storm-exposed roof offers no grip, and "
            "height work without fall protection has no second chance. "
            "Wait for safe conditions and use a professional with "
            "proper access equipment."
        ),
        keywords=(
            "wet, steep roof",
            "wet roof",
            "during the rain",
            "still icy",
            "icy from",
            "frost",
            "third floor roof",
            "do not have a harness",
            "without a harness",
            "no harness",
        ),
    ),
    _r(
        id="major_roof_structural_work",
        hazard="structural_collapse",
        floor=4,
        summary="Large-scale or structural roof work",
        explanation=(
            "Stripping, re-covering or repairing the structure of a "
            "roof means working at height on a surface whose integrity "
            "is itself in question. This needs scaffolding and a "
            "roofing professional."
        ),
        keywords=(
            "large damaged section of roof",
            "strip and re-tile",
            "roof battens",
            "purlin",
            "sagging section of roof",
            "steep two-story",
            "steep two storey",
        ),
    ),
    _r(
        id="major_plumbing_alteration",
        hazard="water_damage",
        floor=4,
        summary="Alteration of mains supply or soil/waste pipework",
        explanation=(
            "Work on the incoming main, the soil stack or waste "
            "connections can flood a property or breach drainage that "
            "the whole building depends on, and is usually notifiable. "
            "Use a qualified plumber."
        ),
        keywords=(
            "main water shutoff",
            "water main",
            "soil stack",
            "waste connections",
            "mains water",
            "whole new bathroom suite",
        ),
    ),
    _r(
        id="uncontrolled_burning",
        hazard="chemical_exposure",
        floor=5,
        summary="Burning treated or painted material",
        explanation=(
            "Burning treated timber or painted offcuts releases arsenic, "
            "copper and lead compounds. It is toxic to everyone "
            "downwind and illegal in many areas. Dispose of it through "
            "a licensed waste facility instead."
        ),
        keywords=("burn a pile", "burning treated", "burn old treated", "burn treated", "bonfire"),
    ),
    # Written against the CONCEPT, not against the examples that were being
    # missed, and validated on a held-out set committed beforehand
    # (ml/data/holdout_rules.json, ml/check_holdout.py). Half that set is
    # adversarial negatives, so an over-broad rule keyed on a bare word like
    # "rotten" or "leaning" fails it.
    _r(
        id="circuit_extension",
        hazard="electrical_shock",
        floor=4,
        summary="Extending fixed wiring rather than replacing an accessory",
        explanation=(
            "Adding a socket, spur or lighting point extends the "
            "circuit rather than replacing a part of it. The existing "
            "circuit has to be assessed for load and protection first, "
            "and this is notifiable work in many places."
        ),
        keywords=(
            "extra socket",
            "additional socket",
            "additional double",
            "spur from",
            "spur off",
            "extend the lighting circuit",
            "extend the circuit",
            "add a new outlet",
            "add a new socket",
            "new outdoor socket",
            "add two downlights",
            "new outlet on",
            "additional outlet",
        ),
    ),
    _r(
        id="decayed_roof_timber",
        hazard="structural_collapse",
        floor=4,
        summary="Decayed load-bearing roof timber",
        explanation=(
            "Rafters, purlins and wall plates carry the roof. Once "
            "they have decayed the roof is already weakened, and "
            "cutting them out removes support while the work is in "
            "progress. This needs temporary propping designed by "
            "someone competent."
        ),
        keywords=(
            "rotten rafter",
            "decayed rafter",
            "rotten roof timber",
            "decayed roof timber",
            "rotten timbers in the flat roof",
            "rotten wall plate",
            "decayed wall plate",
            "rotten roof structure",
            "rotten purlin",
        ),
    ),
    _r(
        id="masonry_wall_instability",
        hazard="structural_collapse",
        floor=4,
        summary="Masonry wall showing lean, movement or through-cracking",
        explanation=(
            "A wall that leans, moves or has cracked through its "
            "mortar joints is no longer stable and can come down "
            "without warning - including onto whoever is working on "
            "it. It needs assessing and rebuilding properly, not "
            "patching."
        ),
        keywords=(
            "leaning wall",
            "leaning garden wall",
            "leaning brick",
            "leaning pier",
            "wall that is leaning",
            "wall is leaning",
            "cracked along the mortar",
            "moves when pushed",
        ),
    ),
    # ---- contaminants / environment --------------------------------------
    _r(
        id="asbestos_disturbance",
        hazard="asbestos_exposure",
        floor=4,
        summary="Possible disturbance of asbestos-containing material",
        explanation=(
            "Disturbing asbestos releases fibres that cause incurable "
            "lung disease decades later. Material of this age must be "
            "surveyed before it is cut, drilled, scraped or removed."
        ),
        keywords=("asbestos", "artex"),
    ),
    _r(
        id="confined_space",
        hazard="confined_space",
        floor=4,
        summary="Entering a confined or poorly ventilated space",
        explanation=(
            "Confined spaces can hold oxygen-deficient or toxic "
            "atmospheres that give no warning. Entry needs atmosphere "
            "testing and someone stationed outside."
        ),
        keywords=(
            "crawl space",
            "crawlspace",
            "deep pit",
            "sealed basement",
            "no ventilation",
            "underfloor void",
            "manhole",
            "soakaway",
        ),
    ),
    _r(
        id="buried_services",
        hazard="buried_utility_strike",
        floor=3,
        summary="Excavation near possible buried services",
        explanation=(
            "Striking a buried gas, electrical or water service while "
            "digging can be fatal. Have services traced and marked "
            "before breaking ground."
        ),
        keywords=("dig", "digging", "trench", "excavate", "break ground"),
    ),
    # -----------------------------------------------------------------------
    # Added 2026-08-01 after auditing the catalog against ml/data/*.json.
    #
    # The first 21 rules were all acute-catastrophic — gas, electrocution,
    # collapse, falls, asbestos, confined space, buried services — and covered
    # 9 of the 16 hazard families the dataset actually uses. Six families had
    # NO rule at all (respiratory_hazard 90 rows, cuts_lacerations 71, fire
    # 50, heavy_object_handling 45, burns 18, hearing_damage 10), which is why
    # keyword rules under-called 37.7% of high-risk rows and why the tagger
    # routed a blowtorch to `asbestos_disturbance`: it was picking the best
    # option from a menu that did not contain the right answer.
    #
    # Keywords stay deliberately multi-word for the reason given above — this
    # layer's value is that it almost never false-fires, and every added rule
    # spends some of that. Floors follow the competence ladder in
    # ml/data/README.md: 3 = needs some experience, 4 = professional only,
    # 5 = nobody attempts this.
    # ---- fire / burns -----------------------------------------------------
    _r(
        id="hot_works_ignition",
        hazard="fire",
        floor=3,
        summary="Open flame or spark-producing work on or near a structure",
        explanation=(
            "Blowtorches, heat guns and grinder sparks start fires in "
            "dust, cavities and old timber that can smoulder unseen for "
            "hours. Clear combustibles, keep an extinguisher to hand and "
            "check the area again well after finishing."
        ),
        keywords=(
            "blow torch",
            "blowtorch",
            "heat gun",
            "soldering torch",
            "welding",
            "angle grinder",
            "cutting disc",
            "burn off the paint",
            "burning off paint",
        ),
    ),
    _r(
        id="flammable_vapour_enclosed",
        hazard="fire",
        floor=4,
        summary="Solvent or fuel vapour in an enclosed space",
        explanation=(
            "Solvent, thinner and adhesive vapours are heavier than air, "
            "pool at floor level and ignite from a pilot light, a switch "
            "or a spark. In an enclosed room the mixture can reach "
            "explosive concentration before you smell a problem."
        ),
        keywords=(
            "solvent based",
            "epoxy floor coating",
            "paint stripper",
            "petrol",
            "white spirit",
            "cellulose thinner",
            "contact adhesive",
        ),
    ),
    _r(
        id="appliance_flex_overload",
        hazard="fire",
        floor=4,
        summary="Overheating plug, socket, flex or extension lead",
        explanation=(
            "A plug, socket or lead that is hot, discoloured or smells "
            "of burning has a loose or overloaded connection and is an "
            "active fire risk. Stop using it, unplug it if you can do so "
            "safely, and have the circuit checked before it is used again."
        ),
        keywords=(
            "hot to touch",
            "extension lead",
            "extension cord",
            "plug is warm",
            "socket is warm",
            "socket feels hot",
            "smells of burning",
            "burning smell",
            "scorch mark",
            "melted plug",
        ),
    ),
    # ---- respiratory ------------------------------------------------------
    _r(
        id="silica_dust",
        hazard="respiratory_hazard",
        floor=3,
        summary="Dry cutting or grinding of masonry, concrete or tile",
        explanation=(
            "Cutting concrete, brick, stone or tile dry releases "
            "respirable crystalline silica, which causes irreversible "
            "lung disease. Use water suppression or on-tool extraction "
            "and a fitted respirator — a nuisance dust mask is not enough."
        ),
        keywords=(
            "cut concrete",
            "cutting concrete",
            "grind concrete",
            "chase the brickwork",
            "cut paving",
            "cut tiles",
            "cutting tiles",
            "dry cut",
        ),
    ),
    _r(
        id="lead_paint_disturbance",
        hazard="respiratory_hazard",
        floor=4,
        summary="Disturbing paint that may contain lead",
        explanation=(
            "Paint from before the 1990s often contains lead. Sanding or "
            "burning it produces fumes and fine dust that are especially "
            "harmful to children and during pregnancy, and in many places "
            "removal from older buildings is a controlled activity."
        ),
        keywords=(
            "lead paint",
            "old paint",
            "flaking paint",
            "victorian",
            "georgian",
            "period property",
            "listed building",
        ),
    ),
    _r(
        id="refrigerant_circuit_work",
        hazard="chemical_exposure",
        floor=4,
        summary="Opening or charging a refrigerant circuit",
        explanation=(
            "Refrigerant causes cold burns and displaces oxygen, and "
            "handling it is restricted to certified technicians almost "
            "everywhere. Charging, recovering or breaking into a sealed "
            "circuit is not DIY work."
        ),
        keywords=(
            "refrigerant",
            "regas",
            "re-gas",
            "recharge the air con",
            "f-gas",
            "freon",
            "heat pump circuit",
            "split system",
        ),
    ),
    _r(
        id="sewage_contamination",
        hazard="respiratory_hazard",
        floor=4,
        summary="Contact with sewage or foul water",
        explanation=(
            "Sewage carries bacteria and viruses that cause serious "
            "illness, and standing foul water may also be live with "
            "nearby electrics. Contaminated areas need professional "
            "cleaning and disinfection, not a mop."
        ),
        keywords=(
            "sewage",
            "foul water",
            "raw waste",
            "soil pipe leak",
            "backing up through the",
            "septic tank",
        ),
    ),
    # ---- cuts / mechanical ------------------------------------------------
    _r(
        id="tree_felling",
        hazard="heavy_object_handling",
        floor=4,
        summary="Felling or dismantling a tree near property",
        explanation=(
            "A tree near buildings, boundaries or overhead lines cannot "
            "be dropped predictably without rigging. Chainsaw kickback "
            "and uncontrolled fall direction are both routinely fatal — "
            "this is arborist work."
        ),
        keywords=(
            "fell a large",
            "fell a tree",
            "felling a tree",
            "cut down the tree",
            "chainsaw",
            "take down a tree",
        ),
    ),
    _r(
        id="powered_cutting_tool",
        hazard="cuts_lacerations",
        floor=2,
        summary="Hand-held powered cutting tool",
        explanation=(
            "Circular saws, grinders and multi-tools bind and kick back "
            "without warning. Clamp the work rather than holding it, keep "
            "both hands on the tool, and wear eye protection — most "
            "injuries happen on the cut that felt routine."
        ),
        keywords=(
            "circular saw",
            "table saw",
            "mitre saw",
            "reciprocating saw",
            "jigsaw",
            "multi tool",
            "bench grinder",
        ),
    ),
    _r(
        id="heavy_manual_handling",
        hazard="heavy_object_handling",
        floor=2,
        summary="Lifting or moving a heavy load",
        explanation=(
            "Baths, slabs, lintels, glazing units and appliances cause "
            "crush and back injuries when handled alone. Plan the route, "
            "use lifting aids and get a second person — most of these "
            "injuries happen in the last metre."
        ),
        keywords=(
            "cast iron bath",
            "paving slab",
            "concrete lintel",
            "kerb stone",
            "glazing unit",
            "railway sleeper",
            "move the fridge",
            "move a piano",
        ),
    ),
    # ---- hearing ----------------------------------------------------------
    # Floor 1 on purpose: sustained noise does not change WHO should attempt
    # a task, so escalating would be wrong under the competence ladder. The
    # rule still fires, so it still reaches `explain()` and the PPE
    # recommendation — a hazard worth telling the user about without moving
    # the risk level is exactly what a floor of MIN_RISK_LEVEL expresses.
    # ---- burns / stored energy --------------------------------------------
    # The last family the audit found with no rule at all (18 dataset rows).
    # Two measured misses drove it: "replace the pressure relief valve on a
    # sealed central heating system" and "replace the immersion heater element
    # in the hot water cylinder", both scored level 1 by keyword rules.
    _r(
        id="pressurised_hot_water_system",
        hazard="burns",
        floor=4,
        summary="Work on a stored or pressurised hot water system",
        explanation=(
            "A sealed or unvented hot water system stores scalding water "
            "under pressure. Opening one that has not been drained and "
            "depressurised can release it violently, and the safety "
            "controls that prevent that are the whole reason these "
            "systems are restricted to qualified installers."
        ),
        keywords=(
            "pressure relief valve",
            "unvented cylinder",
            "sealed central heating",
            "expansion vessel",
            "immersion heater",
            "hot water cylinder",
            "system pressure",
            "megaflo",
        ),
    ),
    _r(
        id="hot_surface_or_liquid",
        hazard="burns",
        floor=2,
        summary="Contact with hot surfaces, liquids or materials",
        explanation=(
            "Flue pipes, radiators, stripped paint and freshly mixed "
            "cement all cause burns that are easy to underestimate. Let "
            "hot work cool before handling it, and wear gloves rated for "
            "the material rather than ordinary work gloves."
        ),
        keywords=(
            "hot flue",
            "molten",
            "boiling water",
            "steam pipe",
            "wet cement",
            "quicklime",
            "hot bitumen",
            "torch on felt",
        ),
    ),
    _r(
        id="sustained_noise_exposure",
        hazard="hearing_damage",
        floor=1,
        summary="Prolonged use of loud power tools",
        explanation=(
            "Breakers, planers, routers and disc cutters exceed safe "
            "noise levels within minutes, and the hearing loss they cause "
            "is permanent and painless as it happens. Wear defenders, not "
            "plugs, for anything sustained."
        ),
        keywords=(
            "breaker hire",
            "kango",
            "jackhammer",
            "disc cutter",
            "planer",
            "router",
            "impact wrench",
        ),
    ),
)

RULES: dict[str, Rule] = {r.id: r for r in _RULES}

# The closed set the LLM hazard tagger is allowed to choose from. Anything
# outside this is discarded - see rules.tag_hazards_via_llm.
VALID_RULE_IDS: frozenset[str] = frozenset(RULES)


# ---------------------------------------------------------------------------
# Safety-critical follow-ups: questions whose answer materially changes risk.
#
# An answer that is MISSING is not the same as an answer that is "no", and
# the two must not be conflated - that exact bug shipped once already and made
# the entire dangerous-task path unreachable (see memory.md, 2026-07-19).
#
#   missing/unknown -> escalate to `floor_when_missing` (worst plausible case)
#   answered False  -> escalate to `floor_when_denied`  (known-unsafe, but known)
#
# Missing scores HIGHER than a "no": an explicit "no" is a known state a user
# can be advised about, whereas an unanswered safety question means the worst
# case cannot be ruled out at all (CLAUDE.md: "treat as worst plausible case,
# never assume safety").
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Followup:
    field: str
    question: str
    floor_when_missing: int
    floor_when_denied: int
    applies_when_rule: tuple[str, ...] = field(default_factory=tuple)
    # Category-based triggering is deliberately unused. It was a fallback
    # while the LLM tagger fell back to "general" for everything; once real
    # categories arrived it started asking nonsense - "is the wall
    # load-bearing?" for a flat-pack wardrobe (carpentry), "is the breaker
    # off?" for changing a light bulb (electrical). Follow-ups are driven by
    # which HAZARD RULE fired, which is the precise signal. Kept on the
    # dataclass only so a future follow-up can opt in explicitly.
    applies_to_categories: tuple[str, ...] = ()


FOLLOWUPS: tuple[Followup, ...] = (
    Followup(
        field="power_isolated",
        question=(
            "Have you confirmed the power to this circuit is fully "
            "isolated at the breaker before starting?"
        ),
        floor_when_missing=5,
        floor_when_denied=3,
        applies_when_rule=(
            "fixed_wiring_work",
            "electrical_work_by_beginner",
            "supply_side_electrical",
            "circuit_extension",
        ),
    ),
    Followup(
        field="load_bearing_confirmed",
        question="Have you confirmed the wall or structure involved is NOT load-bearing?",
        floor_when_missing=5,
        floor_when_denied=4,
        applies_when_rule=("structural_alteration", "masonry_wall_instability"),
    ),
    Followup(
        field="gas_line_present",
        question="Have you confirmed there is no gas line present near this work area?",
        floor_when_missing=5,
        floor_when_denied=4,
        applies_when_rule=("buried_services",),
        applies_to_categories=(),
    ),
    # The gate for `overhead_work_unknown_height`. Answering True (reachable
    # from floor level) closes that gate and the hazard does not apply;
    # answering False means real height work, which is what the floors below
    # escalate. Leaving it unanswered keeps the rule firing at its own floor.
    Followup(
        field="height_access",
        question=(
            "Can you reach this comfortably from floor level or a step "
            "ladder, without needing roof or upper-storey access?"
        ),
        floor_when_missing=3,
        floor_when_denied=3,
        applies_when_rule=("overhead_work_unknown_height",),
    ),
)

FOLLOWUPS_BY_FIELD: dict[str, Followup] = {f.field: f for f in FOLLOWUPS}


# ---------------------------------------------------------------------------
# Hazards that no user answer may ever gate away.
#
# `Rule.gated_by` lets a confirmed-safe answer stop a rule firing, which is
# right for facts the user is authoritative about (can you reach it?). It is
# wrong for these: a user is not a reliable judge of whether a gas escape,
# live conductor or asbestos exposure is really happening, and the cost of
# believing them wrongly is somebody's life. Enforced by a test, not just by
# convention - see tests/test_rule_catalog.py.
# ---------------------------------------------------------------------------
HARD_GATE_RULE_IDS: frozenset[str] = frozenset(
    {
        "active_gas_or_co",
        "water_at_live_electrics",
        "exposed_live_conductor",
        "gas_appliance_work",
        "asbestos_disturbance",
    }
)


# ---------------------------------------------------------------------------
# Follow-up fields the LLM may ASK FOR on its own initiative.
#
# The LLM cannot invent a question, and it cannot suppress one: whatever
# `rules.required_followups()` derives from the fired hazards is asked
# regardless. This set is purely ADDITIVE - it lets the tagger say "the
# description is ambiguous about height, ask about it" instead of resolving
# that ambiguity itself by guessing a tag (rules.md §4: the LLM may phrase
# questions and select from closed sets, never decide risk).
# ---------------------------------------------------------------------------
LLM_SELECTABLE_FOLLOWUP_FIELDS: frozenset[str] = frozenset(FOLLOWUPS_BY_FIELD)
