/**
 * The hardcoded safety rule catalog.
 *
 * ⚠️  GENERATED FILE — DO NOT EDIT BY HAND.
 *     Source:    apps/backend/ai/rule_engine/catalog.py
 *     Generator: tools/generate_catalog_ts.py
 *
 * This module is DATA, not logic. It is the single source of truth for which
 * hazards exist, what each one escalates risk to, and how each is explained to
 * a user. `rules.ts` evaluates it; nothing else may define a hazard.
 *
 * NON-NEGOTIABLE CONSTRAINTS (rules.md §4, CLAUDE.md):
 *
 *   * This catalog is hardcoded and version-controlled. There is deliberately
 *     no `safetyRules` table, no admin UI, and no runtime edit path — changing
 *     a rule means a code change and a code review (srs.md §2.5, §9).
 *   * Every rule can only ever RAISE risk to its `floor`. No rule may lower a
 *     risk level. Callers combine via finalRisk = max(ml, rules).
 *   * The LLM may only ever SELECT rule ids from this set (hazard tagging). It
 *     cannot invent a rule, cannot assign a risk number, and cannot change a
 *     floor. Any id it returns that is not a key of RULES is discarded.
 *
 * JURISDICTION: rules are written in terms of hazard and consequence, not
 * citations to any specific regulation. Thresholds like "gas work requires a
 * professional" are near-universal, but the exact licensing regime differs by
 * country, and this project does not target one — so no rule claims legal
 * authority it cannot back.
 */

/** One hazard rule.
 *
 *  `floor` is the minimum risk level a job matching this rule may receive. It
 *  is a floor, never a ceiling and never an assignment: the engine takes the
 *  maximum across triggered rules, and the caller takes the maximum of that and
 *  the ML prediction.
 */
export interface Rule {
  id: string;
  hazard: string;
  floor: number;
  summary: string;
  explanation: string;
  keywords: readonly string[];
  /** Negative keywords: presence of any means the rule does NOT fire. */
  excludes: readonly string[];
  categories: readonly string[];
  /** If set, fires only for these userSkill values. No rule uses this today
   *  (skill was retired 2026-08-02) but the gate is still enforced. */
  requiresSkill: readonly string[];
  /** Follow-up fields whose CONFIRMED-SAFE answer (true) means this hazard does
   *  not apply, so the rule never fires.
   *
   *  This is NOT de-escalation. A gate refines the TRIGGER CONDITION — it is
   *  `excludes` sourced from a user answer rather than from text — and nothing
   *  lowers a risk level that was already assigned. The safety property that
   *  makes it sound is the default: an UNANSWERED gate still fires the rule, so
   *  the worst plausible case holds until the user rules it out. Silence never
   *  buys a lower risk level; only an explicit answer does. */
  gatedBy: readonly string[];
}

/** A question whose answer materially changes risk.
 *
 *  MISSING and "no" are different states and escalate differently. Missing
 *  scores HIGHER: an explicit "no" is a known state a user can be advised
 *  about, whereas an unanswered safety question means the worst case cannot be
 *  ruled out at all (CLAUDE.md: "treat as worst plausible case, never assume
 *  safety"). Conflating the two once made the entire dangerous-task path
 *  unreachable — see memory.md, 2026-07-19.
 */
export interface Followup {
  field: string;
  question: string;
  floorWhenMissing: number;
  floorWhenDenied: number;
  appliesWhenRule: readonly string[];
  /** Deliberately unused. Category triggering asked nonsense once real
   *  categories arrived ("is the wall load-bearing?" for a flat-pack wardrobe).
   *  Follow-ups are driven by which HAZARD RULE fired, which is the precise
   *  signal. Kept so a future follow-up can opt in explicitly. */
  appliesToCategories: readonly string[];
}

export const MIN_RISK_LEVEL = 1;
export const MAX_RISK_LEVEL = 5;


const RULE_LIST: readonly Rule[] = [
  {
    id: "active_gas_or_co",
    hazard: "gas_leak",
    floor: 5,
    summary: "Suspected gas escape or carbon monoxide",
    explanation: "A suspected gas escape or carbon monoxide presence is an emergency, not a task. Leave the area, avoid switches and naked flames, and contact your gas emergency service.",
    keywords: ["smell gas", "smell of gas", "gas leak", "leaking gas", "carbon monoxide", "co alarm", "lazy flame", "yellow flame", "hissing gas", "gas is hissing"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "gas_appliance_work",
    hazard: "gas_leak",
    floor: 4,
    summary: "Work on gas pipework or a gas appliance",
    explanation: "Work on gas pipework, connections or appliances carries a risk of explosion and poisoning, and in most places is restricted to registered professionals.",
    keywords: ["gas hob", "gas boiler", "gas furnace", "gas fire", "gas supply", "gas pipe", "gas meter", "gas appliance", "gas cooker", "gas water heater", "flue"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "water_at_live_electrics",
    hazard: "electrical_shock",
    floor: 5,
    summary: "Water reaching live electrical equipment",
    explanation: "Water in contact with live electrical equipment is an electrocution and fire risk. Do not touch anything in the area; isolate the supply from a safe location if you can, and get a professional out.",
    keywords: ["water is dripping onto", "dripping onto the fuse", "pouring down onto the light", "water near the fuse", "water leak near", "standing water", "flooded"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "exposed_live_conductor",
    hazard: "electrical_shock",
    floor: 5,
    summary: "Exposed conductors of unverified status",
    explanation: "Exposed wiring must be treated as live until proven otherwise with a tester. Contact can be fatal.",
    keywords: ["live wire", "exposed wire", "bare wire", "sparking", "arcing", "burning smell from the panel"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "supply_side_electrical",
    hazard: "electrical_shock",
    floor: 4,
    summary: "Consumer unit, main panel or supply-side work",
    explanation: "The incoming supply and main board stay live even with the main switch off, so they cannot be made safe by the occupier. This is professional work.",
    keywords: ["consumer unit", "fuse box", "main panel", "electrical panel", "distribution board", "subpanel", "sub panel", "service head", "meter tail", "main breaker", "panel bus"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "fixed_wiring_work",
    hazard: "electrical_shock",
    floor: 3,
    summary: "Work on fixed wiring or accessories",
    explanation: "Working on fixed wiring means working on circuits that may be live. The supply must be isolated and proven dead before anything is disturbed, and faults are often invisible until they matter — have the work checked by a qualified electrician.",
    keywords: ["wiring", "rewire", "rewiring", "circuit", "socket", "outlet", "light fitting", "light fixture", "junction box", "thermostat", "light switch", "dimmer", "chase a channel"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "structural_distress",
    hazard: "structural_collapse",
    floor: 5,
    summary: "Signs of active structural failure",
    explanation: "Spreading cracks, sagging or a floor that moves under load can indicate a structure that is already failing. Stop using the area and get a structural engineer to inspect it before any work is attempted.",
    keywords: ["crack is getting wider", "keeps getting wider", "widening crack", "bulging", "leaning towards", "sagging", "feels bouncy", "came through the roof", "daylight through the ceiling"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "structural_alteration",
    hazard: "structural_collapse",
    floor: 4,
    summary: "Removing or altering a wall or structural element",
    explanation: "Removing a wall or structural member can transfer loads in ways that are not obvious. A structural engineer must confirm what is load-bearing and specify any support.",
    keywords: ["remove a wall", "removing a wall", "knock through", "take down the wall", "take down the stud wall", "demolish", "remove a load-bearing", "chimney breast", "load-bearing", "load bearing", "underpin", "steel lintel"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "fragile_surface",
    hazard: "fall_from_height",
    floor: 5,
    summary: "Working on a fragile roof surface",
    explanation: "Fragile surfaces such as rooflights, perspex panels and cement sheeting will not carry a person's weight and are a leading cause of fatal falls. Do not walk on them.",
    keywords: ["fragile", "perspex", "asbestos cement", "rooflight", "corrugated sheet"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "work_at_height",
    hazard: "fall_from_height",
    floor: 3,
    summary: "Work at height on a roof or upper storey",
    explanation: "Falls from height are among the most common causes of serious injury in construction. Roof and upper-storey work needs proper access equipment and fall protection.",
    keywords: ["roof", "two storey", "two-story", "two story", "three storey", "upper floor", "first floor", "scaffold", "extension ladder", "steep"],
    excludes: ["single storey", "bungalow", "step ladder", "ground level", "from the garden", "low flat", "outbuilding", "binoculars"],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "overhead_work_unknown_height",
    hazard: "fall_from_height",
    floor: 3,
    summary: "Overhead work whose working height has not been established",
    explanation: "Overhead work needs stable, appropriate access equipment. Standing on a chair, a worktop or the top step of a ladder is a common cause of falls. Work from a stable platform you can reach comfortably without stretching.",
    keywords: [],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: ["height_access"],
  },
  {
    id: "unprotected_or_adverse_height_work",
    hazard: "fall_from_height",
    floor: 5,
    summary: "Height work in adverse conditions or without fall protection",
    explanation: "A wet, icy or storm-exposed roof offers no grip, and height work without fall protection has no second chance. Wait for safe conditions and use a professional with proper access equipment.",
    keywords: ["wet, steep roof", "wet roof", "during the rain", "still icy", "icy from", "frost", "third floor roof", "do not have a harness", "without a harness", "no harness"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "major_roof_structural_work",
    hazard: "structural_collapse",
    floor: 4,
    summary: "Large-scale or structural roof work",
    explanation: "Stripping, re-covering or repairing the structure of a roof means working at height on a surface whose integrity is itself in question. This needs scaffolding and a roofing professional.",
    keywords: ["large damaged section of roof", "strip and re-tile", "roof battens", "purlin", "sagging section of roof", "steep two-story", "steep two storey"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "major_plumbing_alteration",
    hazard: "water_damage",
    floor: 4,
    summary: "Alteration of mains supply or soil/waste pipework",
    explanation: "Work on the incoming main, the soil stack or waste connections can flood a property or breach drainage that the whole building depends on, and is usually notifiable. Use a qualified plumber.",
    keywords: ["main water shutoff", "water main", "soil stack", "waste connections", "mains water", "whole new bathroom suite"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "uncontrolled_burning",
    hazard: "chemical_exposure",
    floor: 5,
    summary: "Burning treated or painted material",
    explanation: "Burning treated timber or painted offcuts releases arsenic, copper and lead compounds. It is toxic to everyone downwind and illegal in many areas. Dispose of it through a licensed waste facility instead.",
    keywords: ["burn a pile", "burning treated", "burn old treated", "burn treated", "bonfire"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "circuit_extension",
    hazard: "electrical_shock",
    floor: 4,
    summary: "Extending fixed wiring rather than replacing an accessory",
    explanation: "Adding a socket, spur or lighting point extends the circuit rather than replacing a part of it. The existing circuit has to be assessed for load and protection first, and this is notifiable work in many places.",
    keywords: ["extra socket", "additional socket", "additional double", "spur from", "spur off", "extend the lighting circuit", "extend the circuit", "add a new outlet", "add a new socket", "new outdoor socket", "add two downlights", "new outlet on", "additional outlet"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "decayed_roof_timber",
    hazard: "structural_collapse",
    floor: 4,
    summary: "Decayed load-bearing roof timber",
    explanation: "Rafters, purlins and wall plates carry the roof. Once they have decayed the roof is already weakened, and cutting them out removes support while the work is in progress. This needs temporary propping designed by someone competent.",
    keywords: ["rotten rafter", "decayed rafter", "rotten roof timber", "decayed roof timber", "rotten timbers in the flat roof", "rotten wall plate", "decayed wall plate", "rotten roof structure", "rotten purlin"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "masonry_wall_instability",
    hazard: "structural_collapse",
    floor: 4,
    summary: "Masonry wall showing lean, movement or through-cracking",
    explanation: "A wall that leans, moves or has cracked through its mortar joints is no longer stable and can come down without warning - including onto whoever is working on it. It needs assessing and rebuilding properly, not patching.",
    keywords: ["leaning wall", "leaning garden wall", "leaning brick", "leaning pier", "wall that is leaning", "wall is leaning", "cracked along the mortar", "moves when pushed"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "asbestos_disturbance",
    hazard: "asbestos_exposure",
    floor: 4,
    summary: "Possible disturbance of asbestos-containing material",
    explanation: "Disturbing asbestos releases fibres that cause incurable lung disease decades later. Material of this age must be surveyed before it is cut, drilled, scraped or removed.",
    keywords: ["asbestos", "artex"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "confined_space",
    hazard: "confined_space",
    floor: 4,
    summary: "Entering a confined or poorly ventilated space",
    explanation: "Confined spaces can hold oxygen-deficient or toxic atmospheres that give no warning. Entry needs atmosphere testing and someone stationed outside.",
    keywords: ["crawl space", "crawlspace", "deep pit", "sealed basement", "no ventilation", "underfloor void", "manhole", "soakaway"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "buried_services",
    hazard: "buried_utility_strike",
    floor: 3,
    summary: "Excavation near possible buried services",
    explanation: "Striking a buried gas, electrical or water service while digging can be fatal. Have services traced and marked before breaking ground.",
    keywords: ["dig", "digging", "trench", "excavate", "break ground"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "hot_works_ignition",
    hazard: "fire",
    floor: 3,
    summary: "Open flame or spark-producing work on or near a structure",
    explanation: "Blowtorches, heat guns and grinder sparks start fires in dust, cavities and old timber that can smoulder unseen for hours. Clear combustibles, keep an extinguisher to hand and check the area again well after finishing.",
    keywords: ["blow torch", "blowtorch", "heat gun", "soldering torch", "welding", "angle grinder", "cutting disc", "burn off the paint", "burning off paint"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "flammable_vapour_enclosed",
    hazard: "fire",
    floor: 4,
    summary: "Solvent or fuel vapour in an enclosed space",
    explanation: "Solvent, thinner and adhesive vapours are heavier than air, pool at floor level and ignite from a pilot light, a switch or a spark. In an enclosed room the mixture can reach explosive concentration before you smell a problem.",
    keywords: ["solvent based", "epoxy floor coating", "paint stripper", "petrol", "white spirit", "cellulose thinner", "contact adhesive"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "appliance_flex_overload",
    hazard: "fire",
    floor: 4,
    summary: "Overheating plug, socket, flex or extension lead",
    explanation: "A plug, socket or lead that is hot, discoloured or smells of burning has a loose or overloaded connection and is an active fire risk. Stop using it, unplug it if you can do so safely, and have the circuit checked before it is used again.",
    keywords: ["hot to touch", "extension lead", "extension cord", "plug is warm", "socket is warm", "socket feels hot", "smells of burning", "burning smell", "scorch mark", "melted plug"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "silica_dust",
    hazard: "respiratory_hazard",
    floor: 3,
    summary: "Dry cutting or grinding of masonry, concrete or tile",
    explanation: "Cutting concrete, brick, stone or tile dry releases respirable crystalline silica, which causes irreversible lung disease. Use water suppression or on-tool extraction and a fitted respirator — a nuisance dust mask is not enough.",
    keywords: ["cut concrete", "cutting concrete", "grind concrete", "chase the brickwork", "cut paving", "cut tiles", "cutting tiles", "dry cut"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "lead_paint_disturbance",
    hazard: "respiratory_hazard",
    floor: 4,
    summary: "Disturbing paint that may contain lead",
    explanation: "Paint from before the 1990s often contains lead. Sanding or burning it produces fumes and fine dust that are especially harmful to children and during pregnancy, and in many places removal from older buildings is a controlled activity.",
    keywords: ["lead paint", "old paint", "flaking paint", "victorian", "georgian", "period property", "listed building"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "refrigerant_circuit_work",
    hazard: "chemical_exposure",
    floor: 4,
    summary: "Opening or charging a refrigerant circuit",
    explanation: "Refrigerant causes cold burns and displaces oxygen, and handling it is restricted to certified technicians almost everywhere. Charging, recovering or breaking into a sealed circuit is not DIY work.",
    keywords: ["refrigerant", "regas", "re-gas", "recharge the air con", "f-gas", "freon", "heat pump circuit", "split system"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "sewage_contamination",
    hazard: "respiratory_hazard",
    floor: 4,
    summary: "Contact with sewage or foul water",
    explanation: "Sewage carries bacteria and viruses that cause serious illness, and standing foul water may also be live with nearby electrics. Contaminated areas need professional cleaning and disinfection, not a mop.",
    keywords: ["sewage", "foul water", "raw waste", "soil pipe leak", "backing up through the", "septic tank"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "tree_felling",
    hazard: "heavy_object_handling",
    floor: 4,
    summary: "Felling or dismantling a tree near property",
    explanation: "A tree near buildings, boundaries or overhead lines cannot be dropped predictably without rigging. Chainsaw kickback and uncontrolled fall direction are both routinely fatal — this is arborist work.",
    keywords: ["fell a large", "fell a tree", "felling a tree", "cut down the tree", "chainsaw", "take down a tree"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "powered_cutting_tool",
    hazard: "cuts_lacerations",
    floor: 2,
    summary: "Hand-held powered cutting tool",
    explanation: "Circular saws, grinders and multi-tools bind and kick back without warning. Clamp the work rather than holding it, keep both hands on the tool, and wear eye protection — most injuries happen on the cut that felt routine.",
    keywords: ["circular saw", "table saw", "mitre saw", "reciprocating saw", "jigsaw", "multi tool", "bench grinder"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "heavy_manual_handling",
    hazard: "heavy_object_handling",
    floor: 2,
    summary: "Lifting or moving a heavy load",
    explanation: "Baths, slabs, lintels, glazing units and appliances cause crush and back injuries when handled alone. Plan the route, use lifting aids and get a second person — most of these injuries happen in the last metre.",
    keywords: ["cast iron bath", "paving slab", "concrete lintel", "kerb stone", "glazing unit", "railway sleeper", "move the fridge", "move a piano"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "pressurised_hot_water_system",
    hazard: "burns",
    floor: 4,
    summary: "Work on a stored or pressurised hot water system",
    explanation: "A sealed or unvented hot water system stores scalding water under pressure. Opening one that has not been drained and depressurised can release it violently, and the safety controls that prevent that are the whole reason these systems are restricted to qualified installers.",
    keywords: ["pressure relief valve", "unvented cylinder", "sealed central heating", "expansion vessel", "immersion heater", "hot water cylinder", "system pressure", "megaflo"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "hot_surface_or_liquid",
    hazard: "burns",
    floor: 2,
    summary: "Contact with hot surfaces, liquids or materials",
    explanation: "Flue pipes, radiators, stripped paint and freshly mixed cement all cause burns that are easy to underestimate. Let hot work cool before handling it, and wear gloves rated for the material rather than ordinary work gloves.",
    keywords: ["hot flue", "molten", "boiling water", "steam pipe", "wet cement", "quicklime", "hot bitumen", "torch on felt"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
  {
    id: "sustained_noise_exposure",
    hazard: "hearing_damage",
    floor: 1,
    summary: "Prolonged use of loud power tools",
    explanation: "Breakers, planers, routers and disc cutters exceed safe noise levels within minutes, and the hearing loss they cause is permanent and painless as it happens. Wear defenders, not plugs, for anything sustained.",
    keywords: ["breaker hire", "kango", "jackhammer", "disc cutter", "planer", "router", "impact wrench"],
    excludes: [],
    categories: [],
    requiresSkill: [],
    gatedBy: [],
  },
];

export const FOLLOWUPS: readonly Followup[] = [
  {
    field: "power_isolated",
    question: "Have you confirmed the power to this circuit is fully isolated at the breaker before starting?",
    floorWhenMissing: 5,
    floorWhenDenied: 3,
    appliesWhenRule: ["fixed_wiring_work", "supply_side_electrical", "circuit_extension"],
    appliesToCategories: [],
  },
  {
    field: "load_bearing_confirmed",
    question: "Have you confirmed the wall or structure involved is NOT load-bearing?",
    floorWhenMissing: 5,
    floorWhenDenied: 4,
    appliesWhenRule: ["structural_alteration", "masonry_wall_instability"],
    appliesToCategories: [],
  },
  {
    field: "gas_line_present",
    question: "Have you confirmed there is no gas line present near this work area?",
    floorWhenMissing: 5,
    floorWhenDenied: 4,
    appliesWhenRule: ["buried_services"],
    appliesToCategories: [],
  },
  {
    field: "height_access",
    question: "Can you reach this comfortably from floor level or a step ladder, without needing roof or upper-storey access?",
    floorWhenMissing: 3,
    floorWhenDenied: 3,
    appliesWhenRule: ["overhead_work_unknown_height"],
    appliesToCategories: [],
  },
];


export const RULES: Readonly<Record<string, Rule>> = Object.freeze(
  Object.fromEntries(RULE_LIST.map((r) => [r.id, r])),
);

/** The closed set the LLM hazard tagger may choose from. Anything outside this
 *  is discarded — it is a model error, never a new rule. */
export const VALID_RULE_IDS: ReadonlySet<string> = new Set(RULE_LIST.map((r) => r.id));

export const FOLLOWUPS_BY_FIELD: Readonly<Record<string, Followup>> = Object.freeze(
  Object.fromEntries(FOLLOWUPS.map((f) => [f.field, f])),
);

/** Hazards that no user answer may ever gate away.
 *
 *  `Rule.gatedBy` is right for facts the user is authoritative about (can you
 *  reach it?). It is wrong for these: a user is not a reliable judge of whether
 *  a gas escape, live conductor or asbestos exposure is really happening, and
 *  the cost of believing them wrongly is somebody's life. Enforced by a test,
 *  not just by convention. */
export const HARD_GATE_RULE_IDS: ReadonlySet<string> = new Set(["active_gas_or_co", "asbestos_disturbance", "exposed_live_conductor", "gas_appliance_work", "water_at_live_electrics"]);

/** Follow-up fields the LLM may ASK FOR on its own initiative.
 *
 *  Purely ADDITIVE: the LLM cannot invent a question, and cannot suppress one —
 *  whatever `requiredFollowups()` derives from the fired hazards is asked
 *  regardless. This lets the tagger say "the description is ambiguous about
 *  height, ask about it" instead of resolving that ambiguity by guessing a tag. */
export const LLM_SELECTABLE_FOLLOWUP_FIELDS: ReadonlySet<string> = new Set(["gas_line_present", "height_access", "load_bearing_confirmed", "power_isolated"]);
