/**
 * Content for the homepage register.
 *
 * TWO KINDS OF CONTENT LIVE HERE AND THEY ARE NOT INTERCHANGEABLE:
 *
 * 1. FACTS ABOUT THE SHIPPED SYSTEM (`SCALE`, `LEDGER_FACTS`, the rule ids,
 *    floors, summaries and follow-up questions quoted inside `CASES`). Every
 *    one of these is copied from `convex/ai/ruleEngine/catalog.ts` or from a
 *    verification gate that actually runs. They are marketing-visible claims,
 *    so they must stay true: if a rule's `floor` changes, or a rule is added or
 *    removed, the counts in `SCALE` and the quoted floors below go stale and
 *    the page starts lying about what the product does. Re-derive them from the
 *    catalog rather than editing them to taste.
 *
 * 2. SYNTHETIC CASE ENTRIES (the task text, ref numbers and dates in `CASES`).
 *    These are authored illustrations, not real user assessments, and the page
 *    labels them as such in the register head and again in the entry rail.
 *    Never present them as usage data, and never add a case that implies an
 *    outcome the engine would not actually produce — each one below was
 *    hand-checked against the catalog:
 *
 *      REG-0114  fixed_wiring_work floor 3, power_isolated answered "yes"
 *                (no escalation) → max(ml 2, rules 3) = 3
 *      REG-0207  structural_alteration floor 4, load_bearing_confirmed answered
 *                "unsure" → floorWhenMissing 5 → max(ml 3, rules 5) = 5
 *      REG-0341  gas_appliance_work floor 4, no follow-up applies
 *                → max(ml 2, rules 4) = 4
 *
 * What must NOT appear here, ever: user counts, testimonials, customer names,
 * press, certification claims, or an accuracy figure. The ≥95% recall number in
 * `prd.md` §7 is a provisional target pending supervisor confirmation, not a
 * measured result, and is deliberately absent.
 */

import type { RiskLevel } from "@/lib/riskLevels";

/** One rung of the classification scale, with the number of catalog rules whose
 *  `floor` is that level. Counts derived from `catalog.ts` (34 rules total). */
export interface ScaleRung {
  level: RiskLevel;
  meaning: string;
  /** How many hardcoded hazard rules escalate to exactly this level. */
  ruleCount: number;
}

export const SCALE: readonly ScaleRung[] = [
  { level: 1, meaning: "Proceed with normal care.", ruleCount: 1 },
  { level: 2, meaning: "Proceed with experienced help.", ruleCount: 3 },
  { level: 3, meaning: "Consider hiring a professional.", ruleCount: 6 },
  { level: 4, meaning: "Do not attempt without a professional.", ruleCount: 17 },
  { level: 5, meaning: "Stop; contact a professional immediately.", ruleCount: 7 },
];

/** A follow-up as it was answered in an illustrative case. */
export interface CaseFollowup {
  /** The follow-up's `field` in the catalog — a real key, quoted. */
  field: string;
  /** The catalog's own wording of the question, quoted verbatim. */
  question: string;
  answer: "yes" | "no" | "unsure";
  /** What that answer did to the floor, in the product's own terms. */
  effect: string;
  /** True when this answer is what set the final level. */
  decisive: boolean;
}

/** A rule as it fired in an illustrative case. */
export interface CaseRule {
  id: string;
  summary: string;
  floor: RiskLevel;
}

export interface CaseEntry {
  ref: string;
  date: string;
  category: string;
  /** The task in the words a user would actually type. */
  task: string;
  rules: readonly CaseRule[];
  followups: readonly CaseFollowup[];
  ml: RiskLevel;
  rulesResult: RiskLevel;
  final: RiskLevel;
  /** One line naming what this entry demonstrates about the engine. */
  shows: string;
}

export const CASES: readonly CaseEntry[] = [
  {
    ref: "REG-0114",
    date: "Electrical",
    category: "Electrical",
    task: "The light switch in the hallway is cracked and I want to swap it for a dimmer.",
    rules: [
      {
        id: "fixed_wiring_work",
        summary: "Work on fixed wiring or accessories",
        floor: 3,
      },
    ],
    followups: [
      {
        field: "power_isolated",
        question:
          "Is the power to this circuit switched off and isolated at the breaker?",
        answer: "yes",
        effect: "No escalation. The hazard is not ruled out, only the live-work risk.",
        decisive: false,
      },
    ],
    ml: 2,
    rulesResult: 3,
    final: 3,
    shows:
      "The classifier read a routine swap. The catalog knows fixed wiring is never routine, and raised it.",
  },
  {
    ref: "REG-0207",
    date: "Carpentry",
    category: "Carpentry",
    task: "Taking out the wall between the kitchen and the dining room this weekend.",
    rules: [
      {
        id: "structural_alteration",
        summary: "Removing or altering a wall or structural element",
        floor: 4,
      },
    ],
    followups: [
      {
        field: "load_bearing_confirmed",
        question:
          "Is the wall or structure you will be working on non-load-bearing?",
        answer: "unsure",
        effect: "Escalated to 5 — the worst plausible case, exactly as an unanswered question would.",
        decisive: true,
      },
    ],
    ml: 3,
    rulesResult: 5,
    final: 5,
    shows:
      "Not knowing whether the wall holds the house up is treated as though it does. Clause 1.",
  },
  {
    ref: "REG-0341",
    date: "Plumbing",
    category: "Plumbing",
    task: "Just moving the gas hob two feet along the counter, the pipe looks long enough.",
    rules: [
      {
        id: "gas_appliance_work",
        summary: "Work on gas pipework or a gas appliance",
        floor: 4,
      },
    ],
    followups: [],
    ml: 2,
    rulesResult: 4,
    final: 4,
    shows:
      "“Just moving” read as low risk to the model. Gas work is a hardcoded floor and the model does not get a vote.",
  },
];

/** The standing clauses of the register: how a verdict is reached, in the terms
 *  the codebase actually enforces. Numbered because the case entries cite them. */
export interface Clause {
  n: number;
  title: string;
  body: string;
}

export const CLAUSES: readonly Clause[] = [
  {
    n: 1,
    title: "Uncertainty escalates",
    body: "A safety question has four answers, not two. Yes, no, unsure, and unanswered are all different states. Unsure and unanswered both resolve to the worst plausible case — silence never buys a lower risk level.",
  },
  {
    n: 2,
    title: "The engine only ever raises",
    body: "The final verdict is the higher of what the classifier predicted and what the rule catalog requires. A rule can lift a level. Nothing in the system can lower one.",
  },
  {
    n: 3,
    title: "The language model never decides",
    body: "It phrases the follow-up questions and tags which of the hardcoded hazard rules match your description. It cannot invent a rule, change a floor, or pick a risk number. Anything it returns outside the catalog is discarded.",
  },
  {
    n: 4,
    title: "Failure is visible",
    body: "If the pipeline breaks, the assessment is marked failed and the DIY recommendation is withheld. There is no quiet fallback to a reassuring answer.",
  },
];

/** Verifiable properties of the shipped system. Each is checkable in the repo;
 *  none is a usage, adoption, or accuracy claim. */
export const LEDGER_FACTS: readonly { value: string; label: string }[] = [
  { value: "34", label: "hardcoded hazard rules, changed only by code review" },
  { value: "5", label: "risk levels, fixed order, never reassigned" },
  { value: "2,895", label: "rule evaluations replayed against a reviewed baseline" },
  { value: "1.55e-15", label: "largest drift between the shipped classifier and scikit-learn" },
];

/** What the register does not cover. Straight from `prd.md` §4 — stated on the
 *  page because a scope note is part of the form, not a disclaimer bolted on. */
export const OUT_OF_SCOPE: readonly string[] = [
  "Booking, quoting, or connecting you with a contractor",
  "Payments, deposits, or escrow of any kind",
  "Legally certified permit or building-control verification",
  "Diagnosing a structure from a photograph",
  "Any guarantee of legal compliance or of a professional’s work",
];
