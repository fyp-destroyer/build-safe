/**
 * Evidence behind each catalog rule's floor. DEVELOPER-FACING ONLY.
 *
 * WHY THIS IS A SEPARATE FILE AND NOT A FIELD ON `Rule`
 * -----------------------------------------------------
 * catalog.ts states a deliberate design decision in its header: rules are
 * written in terms of hazard and consequence, NOT citations to any specific
 * regulation, because the exact licensing regime differs by country and this
 * project does not target one — "no rule claims legal authority it cannot back."
 *
 * That decision is correct and this file does not overturn it. A user in the US
 * must never be shown a floor justified by a UK statutory instrument. So:
 *
 *   - `Rule.explanation` (user-facing) stays jurisdiction-neutral. Unchanged.
 *   - This map (developer-facing) records WHY each floor is what it is, so the
 *     catalog can be reviewed against evidence rather than against memory.
 *
 * Keeping it out of `Rule` also means nothing here can perturb a floor: the
 * risk-bearing data structure is not touched at all.
 *
 * Every `sources` id must exist in `ml/data/sources.json`, which carries the
 * publisher, URL, jurisdiction and verification date. `severity` and
 * `restriction` use the bands defined in `ml/data/rubric.md` — the same two
 * axes the dataset labels are derived from, so the engine and the training data
 * are justified on one scheme rather than two.
 *
 * NOT a runtime input. Nothing in rules.ts imports this; it is documentation
 * with a compile-time completeness check.
 */

import { RULES } from "./catalog";

export interface RuleBasis {
  /** Severity band from rubric.md: S1-S4. */
  severity: "S1" | "S2" | "S3" | "S4";
  /** Restriction class from rubric.md: R0 | Rw | R1w | R1 | R2 | R3. */
  restriction: "R0" | "Rw" | "R1w" | "R1" | "R2" | "R3";
  /** Source ids from ml/data/sources.json. */
  sources: readonly string[];
  /** Why this floor, in one sentence, in terms of hazard and consequence. */
  rationale: string;
  /** Set where the evidence is weaker than the rest, so review can target it. */
  caveat?: string;
}

export const RULE_BASIS: Readonly<Record<string, RuleBasis>> = Object.freeze({
  active_gas_or_co: {
    severity: "S4", restriction: "R3",
    sources: ["gas-safety-regs-1998"],
    rationale:
      "A suspected escape or CO presence is an evacuate-and-call emergency: the correct " +
      "action is identical for a beginner and a registered engineer, which is what floor 5 means.",
  },
  gas_appliance_work: {
    severity: "S4", restriction: "R2",
    sources: ["gas-safety-regs-1998"],
    rationale:
      "Work on gas fittings and appliances is restricted to registered engineers and needs " +
      "test equipment a householder does not have.",
  },
  water_at_live_electrics: {
    severity: "S3", restriction: "R3",
    sources: ["cpsc-neiss-electrical", "approved-document-p"],
    rationale:
      "Water actively reaching live electrics is an energised fault in progress; the first " +
      "action is isolating the supply, not starting work.",
  },
  exposed_live_conductor: {
    severity: "S3", restriction: "R3",
    sources: ["cpsc-neiss-electrical"],
    rationale:
      "Conductors of unverified status must be treated as live. Nothing is safe to touch until " +
      "the supply is proven dead.",
  },
  supply_side_electrical: {
    severity: "S3", restriction: "R1",
    sources: ["approved-document-p"],
    rationale:
      "Consumer-unit and supply-side work is notifiable, and the service head cannot be isolated " +
      "by the occupier at all.",
  },
  fixed_wiring_work: {
    severity: "S3", restriction: "Rw",
    sources: ["approved-document-p", "cpsc-neiss-electrical"],
    rationale:
      "Work on fixed wiring is work on conductors that may be live, even where it is not notifiable.",
    caveat:
      "Ungated on purpose (`gatedBy: []`): the engine must not lower a level on the strength of a " +
      "free-text isolation claim. The DATASET does credit a stated-and-verified isolation, so " +
      "seed labels of 2 here are expected and are reconciled by max(ML, rules). See " +
      "ml/review_high_risk.py's `fixed-wiring-work` rule.",
  },
  circuit_extension: {
    severity: "S3", restriction: "R1",
    sources: ["approved-document-p"],
    rationale:
      "Extending a circuit adds load and changes protection requirements; notifiable work requiring " +
      "certification by a registered competent person.",
  },
  appliance_flex_overload: {
    severity: "S3", restriction: "R0",
    sources: ["cpsc-neiss-electrical"],
    rationale:
      "Overloaded flex and daisy-chained extensions are a documented domestic ignition source; the " +
      "hazard is fire rather than shock.",
  },
  structural_distress: {
    severity: "S4", restriction: "R3",
    sources: ["hse-fatal-injuries", "approved-document-a"],
    rationale:
      "Movement already in progress — bulging, spreading, widening — means the failure mode is " +
      "active. Leave and get it assessed.",
  },
  structural_alteration: {
    severity: "S4", restriction: "R1",
    sources: ["approved-document-a"],
    rationale:
      "Altering a load path requires engineered temporary support and building control sign-off.",
  },
  masonry_wall_instability: {
    severity: "S4", restriction: "R1",
    sources: ["approved-document-a", "hse-fatal-injuries"],
    rationale:
      "A leaning or cracked retaining wall is holding a load it is no longer shaped to hold; collapse " +
      "is a crush hazard to whoever is beside it.",
  },
  major_roof_structural_work: {
    severity: "S4", restriction: "R1",
    sources: ["approved-document-a", "hsg33"],
    rationale:
      "Cutting or altering roof structure combines a load-path change with a working position at height.",
  },
  decayed_roof_timber: {
    severity: "S4", restriction: "R1",
    sources: ["approved-document-a", "hsg33"],
    rationale:
      "Decayed structural timber gives no reliable warning before it fails, and it is being stood on.",
  },
  fragile_surface: {
    severity: "S4", restriction: "R3",
    sources: ["hsg33", "geis5"],
    rationale:
      "HSG33 paras 170-202 and GEIS5: the control for a fragile surface is staging or covers, not care. " +
      "Walking on one is the failure mode itself, at any skill level.",
  },
  unprotected_or_adverse_height_work: {
    severity: "S4", restriction: "R3",
    sources: ["hsg33", "hse-fatal-injuries"],
    rationale:
      "Wet, icy or unprotected height work is a defer-until-safe situation. The same task is a 3 or 4 " +
      "in good conditions, which is exactly what floor 5 encodes: not right now.",
  },
  work_at_height: {
    severity: "S3", restriction: "R0",
    sources: ["hse-fatal-injuries", "hsg33"],
    rationale:
      "Falls from height caused 31 of 126 GB worker deaths in 2025/26, the single most common cause.",
    caveat: "HSE figures are provisional until July 2027.",
  },
  overhead_work_unknown_height: {
    severity: "S3", restriction: "R0",
    sources: ["hse-fatal-injuries"],
    rationale:
      "Height is unstated, so the worst plausible working position applies until the user says otherwise.",
  },
  major_plumbing_alteration: {
    severity: "S2", restriction: "R1w",
    sources: ["water-fittings-regs-1999", "approved-document-g"],
    rationale:
      "Altering supply or drainage layout is notifiable to the water undertaker; unvented hot water " +
      "may only be installed by a competent person.",
    caveat:
      "Floor 4 exceeds the R1w floor of 3 that the dataset rubric derives for notification-only duties. " +
      "The extra band comes from the water-damage consequence compounding, not from the regulation.",
  },
  asbestos_disturbance: {
    severity: "S4", restriction: "R2",
    sources: ["car-2012"],
    rationale:
      "Disturbing asbestos-containing material requires controlled conditions, and many categories " +
      "require a licensed contractor. The disease is fatal and long-latency, so there is no feedback " +
      "that would tell someone they got it wrong.",
  },
  confined_space: {
    severity: "S4", restriction: "R2",
    sources: ["confined-spaces-regs-1997"],
    rationale:
      "Atmosphere testing and rescue arrangements must be in place BEFORE entry. Most confined-space " +
      "deaths include a would-be rescuer.",
  },
  buried_services: {
    severity: "S4", restriction: "R0",
    sources: ["hsg47"],
    rationale:
      "HSG47: plans alone are insufficient, locating equipment is required, and a service is positively " +
      "located only once safely exposed. A buried cable cannot be told from a pipe by sight.",
    caveat:
      "Floor 3 sits below the S4 the rubric derives, because the rule fires on intent to dig rather " +
      "than on confirmed proximity to a service.",
  },
  uncontrolled_burning: {
    severity: "S4", restriction: "R3",
    sources: ["coshh-2002", "lead-at-work-regs-2002"],
    rationale:
      "Burning treated or painted timber releases arsenic, copper and lead fume, and the exposure is " +
      "uncontrolled and shared with neighbours.",
  },
  hot_works_ignition: {
    severity: "S3", restriction: "R0",
    sources: ["coshh-2002"],
    rationale:
      "Open flame or torch-applied work near combustible fabric ignites voids that smoulder unseen.",
  },
  flammable_vapour_enclosed: {
    severity: "S4", restriction: "R2",
    sources: ["coshh-2002"],
    rationale:
      "COSHH reg. 7 puts ventilation and engineering controls above PPE, and solvents always require " +
      "ventilation. In a sealed space vapour reaches explosive concentration and a filter mask does nothing.",
  },
  silica_dust: {
    severity: "S3", restriction: "R0",
    sources: ["osha-silica-1926-1153"],
    rationale:
      "29 CFR 1926.1153: cutting or grinding masonry, concrete, brick or tile releases respirable " +
      "crystalline silica. PEL 50 ug/m3 over 8h. Table 1 prescribes water-fed blades or " +
      "shroud-and-vacuum collection — a dust mask alone is not the control.",
  },
  lead_paint_disturbance: {
    severity: "S4", restriction: "R0",
    sources: ["lead-at-work-regs-2002"],
    rationale:
      "Lead pigment was in domestic paint until the 1960s and not gone from common paints until the " +
      "early 1980s. HSE requires on-tool extraction, wet abrasive methods and APF-20 RPE, and forbids " +
      "blow lamps or hot air above 500 C.",
  },
  refrigerant_circuit_work: {
    severity: "S3", restriction: "R2",
    sources: ["fgas-qualifications"],
    rationale:
      "It is against the law to work on equipment containing fluorinated gases without the required " +
      "qualification. Applies to the sealed circuit — not to cleaning a filter or a coil.",
  },
  sewage_contamination: {
    severity: "S3", restriction: "R0",
    sources: ["coshh-2002"],
    rationale:
      "Foul water is a biological hazard under COSHH, and backflow into living space is a " +
      "contamination event rather than a plumbing repair.",
  },
  tree_felling: {
    severity: "S4", restriction: "R0",
    sources: ["cpsc-power-tools-2003h054", "hse-fatal-injuries"],
    rationale:
      "Chainsaw use combines an uncontrolled cutting hazard with a falling load whose direction is " +
      "decided before the cut and cannot be corrected afterwards.",
    caveat:
      "No jurisdiction-neutral restriction is cited, though tree work near property is separately " +
      "constrained by preservation orders in many jurisdictions. Floor rests on severity alone.",
  },
  powered_cutting_tool: {
    severity: "S2", restriction: "R0",
    sources: ["cpsc-power-tools-2003h054", "cpsc-neiss"],
    rationale:
      "Hand-held powered cutting is the highest-volume injury mechanism in the NEISS workshop " +
      "category. Floor 2 reflects the typical presentation; amputation is the tail, not the median.",
    caveat:
      "The dataset rubric derives S3 for the same mechanism (worst CREDIBLE outcome), against a floor " +
      "of 2 here (worst TYPICAL outcome). This is a known, deliberate divergence and the largest " +
      "single cluster in the rubric review queue — see ml/data/rubric.md.",
  },
  heavy_manual_handling: {
    severity: "S2", restriction: "R0",
    sources: ["manual-handling-regs-1992"],
    rationale:
      "L23 gives guideline filter figures of 25kg (men) and 16kg (women) for lifting close to the body " +
      "at waist height under ideal conditions.",
    caveat:
      "Those are SCREENING FILTERS, not safe limits, and the Regulations deliberately set no weight " +
      "limit. Never render this as 'the legal limit is 25kg'.",
  },
  pressurised_hot_water_system: {
    severity: "S3", restriction: "R2",
    sources: ["approved-document-g"],
    rationale:
      "Part G3: an unvented hot water system may only be installed by a competent person, because an " +
      "incorrectly installed cylinder can explode or discharge scalding water.",
  },
  hot_surface_or_liquid: {
    severity: "S2", restriction: "R0",
    sources: ["cpsc-neiss"],
    rationale: "Thermal burn requiring medical attention, with full recovery expected.",
  },
  sustained_noise_exposure: {
    severity: "S2", restriction: "R0",
    sources: ["noise-regs-2005"],
    rationale:
      "Lower exposure action value 80 dB(A), upper 85 dB(A) at which hearing protection must be " +
      "provided and enforced, exposure limit value 87 dB(A).",
    caveat:
      "Floor 1 sits below the S2 the rubric derives. Defensible: noise causes cumulative impairment " +
      "rather than an acute injury, so it should inform the PPE recommendation without escalating the " +
      "risk level on its own. Flagged because it is the only rule whose floor is below its severity band.",
  },
} satisfies Record<string, RuleBasis>);

/**
 * Completeness check. Throws at import time if a rule has no recorded basis or
 * a basis names a rule that no longer exists.
 *
 * Deliberately a throw and not a lint: an unjustified floor is exactly the kind
 * of thing that should stop a deploy, and adding a catalog rule without
 * recording why its floor is what it is is how the catalog drifts back to
 * being unexaminable.
 */
const ruleIds = new Set(Object.keys(RULES));
const basisIds = new Set(Object.keys(RULE_BASIS));

const missing = [...ruleIds].filter((id) => !basisIds.has(id)).sort();
const orphaned = [...basisIds].filter((id) => !ruleIds.has(id)).sort();

if (missing.length > 0 || orphaned.length > 0) {
  throw new Error(
    "catalogBasis.ts is out of sync with catalog.ts" +
      (missing.length ? `\n  rules with no recorded basis: ${JSON.stringify(missing)}` : "") +
      (orphaned.length ? `\n  basis entries for unknown rules: ${JSON.stringify(orphaned)}` : ""),
  );
}
