/**
 * LLM-assisted category tagging + follow-up question phrasing.
 *
 * **What this module is allowed to do, and nothing more** (rules.md §4 /
 * CLAUDE.md): (a) pick a category string from the fixed, closed 9-value
 * `TASK_CATEGORIES` set for a free-text task description ("tagging"), (b) tag
 * which *existing* catalog hazard rule ids apply to a description, (c) select
 * which *existing* follow-up fields to ask about when the description is
 * ambiguous, and (d) phrase the natural-language wording of a question about an
 * *already-hardcoded* follow-up field.
 *
 * It cannot invent a rule or a question, cannot assign or suggest a risk number,
 * and cannot change any escalation floor: every id it proposes is filtered
 * against `VALID_RULE_IDS` (or `LLM_SELECTABLE_FOLLOWUP_FIELDS`) before it can
 * influence anything, and the floors themselves are hardcoded in catalog.ts.
 * Every contribution is additive only — it can cause a hardcoded rule to fire
 * that keyword matching missed, or a hardcoded question to be asked that the
 * catalog did not derive, never suppress either.
 *
 * EVIDENCE GROUNDING
 * ------------------
 * Every proposed hazard must quote the user's own words that justify it, and
 * that quote is verified as a literal substring of the description before the
 * tag is accepted. A model cannot quote text the user never wrote, so a hazard
 * it merely inferred is discarded mechanically rather than argued out of it in
 * the prompt.
 *
 * This exists because prose alone did not hold. The previous prompt already said
 * "do not tag a hazard the description does not report" and still returned
 * `work_at_height` for "how do I change my light bulb" — the model reasoned bulb
 * → ceiling → overhead → height and tagged a level-3 hazard the user had said
 * nothing about. Where a hazard depends on a fact the user has not stated, the
 * model now puts the matching follow-up field in `ask` instead of guessing:
 * uncertainty becomes a question, not a tag.
 *
 * Because which follow-ups are required is derived from which hazard rules fired
 * (`requiredFollowups`), tagging does indirectly widen the set of questions
 * asked. That is intended, but it means the tagged set must be *identical*
 * everywhere it is consulted — convex/jobs.ts resolves it once per job and
 * persists it for exactly that reason.
 *
 * Every call goes through `generateStructured`, which never throws and returns
 * `null` on any failure — every function here has a hardcoded, safe fallback for
 * that case and never blocks or errors the job flow just because the LLM is
 * unavailable.
 */

import { z } from "zod";
import { generateStructured } from "../llm/client";
import {
  FOLLOWUPS_BY_FIELD,
  LLM_SELECTABLE_FOLLOWUP_FIELDS,
  RULES,
  VALID_RULE_IDS,
} from "./catalog";

/** The 9 categories locked in phases.md Phase 1 (was schemas/job.py). */
export const TASK_CATEGORIES = [
  "electrical",
  "plumbing",
  "carpentry",
  "masonry",
  "painting",
  "tiling",
  "hvac",
  "roofing",
  "general",
] as const;

export type TaskCategory = (typeof TASK_CATEGORIES)[number];

const FALLBACK_CATEGORY: TaskCategory = "general";

/**
 * Hardcoded default phrasings, keyed by the same field names hardcoded in
 * catalog.ts. Used whenever the LLM is unavailable or returns an empty answer —
 * the flow must never block just because the LLM is down.
 */
const DEFAULT_FOLLOWUP_QUESTIONS: Record<string, string> = {
  power_isolated:
    "Have you confirmed the power to this circuit is fully isolated at the breaker before starting?",
  load_bearing_confirmed:
    "Have you confirmed the wall or structure involved is NOT load-bearing?",
  gas_line_present: "Have you confirmed there is no gas line present near this work area?",
  height_access:
    "Can you reach this comfortably from floor level or a step ladder, without needing roof or upper-storey access?",
};

const CategoryTag = z.object({ category: z.string() });
const PhrasedQuestion = z.object({ question: z.string() });

/**
 * One proposed hazard, with the user's own words that justify it.
 *
 * `evidence` must be a verbatim span from the task description. It is verified
 * as a substring before the tag is accepted — see `evidenceSupports`. This is
 * what stops the model tagging a hazard it merely imagined: it cannot quote text
 * the user never wrote.
 */
const HazardTag = z.object({
  rule_id: z.string(),
  evidence: z.string(),
});

/**
 * `ask` lets the model route an AMBIGUITY into a question instead of resolving
 * it by guessing a tag. Fields are validated against the closed
 * `LLM_SELECTABLE_FOLLOWUP_FIELDS` set and are additive only.
 */
const HazardTags = z.object({
  tags: z.array(HazardTag).default([]),
  ask: z.array(z.string()).default([]),
});

/** What the tagger resolved for a job: hazards, plus questions to ask. */
export interface TagResult {
  ruleIds: string[];
  askFields: string[];
}

/**
 * Classify a free-text task description into one of the fixed 9 categories.
 *
 * Defense in depth: even though `generateStructured` constrains the JSON *shape*,
 * the returned `category` string is still explicitly checked against
 * TASK_CATEGORIES (case-insensitive) before being trusted — an LLM-invented
 * category string must never reach the database. Falls back to "general" if the
 * LLM is unavailable or returns anything outside the fixed set.
 */
export async function tagCategory(description: string): Promise<TaskCategory> {
  const prompt =
    "Classify the following DIY/construction task description into exactly one " +
    `of these fixed categories: ${TASK_CATEGORIES.join(", ")}.\n` +
    "Respond with only the single best-matching category string from that exact " +
    "list — never invent a category outside this list.\n\n" +
    `Task description: ${JSON.stringify(description)}`;

  const result = await generateStructured(prompt, CategoryTag, "CategoryTag");
  if (result === null) {
    console.warn("LLM category tagging unavailable; falling back to 'general'.");
    return FALLBACK_CATEGORY;
  }

  const normalized = result.category.trim().toLowerCase();
  if (!(TASK_CATEGORIES as readonly string[]).includes(normalized)) {
    console.warn(
      `LLM returned a category outside the fixed set ` +
        `(${JSON.stringify(result.category)}); falling back to 'general'.`,
    );
    return FALLBACK_CATEGORY;
  }

  return normalized as TaskCategory;
}

/**
 * Phrase a natural, user-facing yes/no-style question about an
 * already-hardcoded safety-critical follow-up field.
 *
 * This function has zero say over *whether* `field` is required or how a missing
 * answer affects risk — it only supplies wording. Falls back to a hardcoded
 * default phrasing if the LLM is unavailable or returns an empty question.
 */
export async function phraseFollowupQuestion(field: string, category: string): Promise<string> {
  const fallback =
    DEFAULT_FOLLOWUP_QUESTIONS[field] ?? `Please confirm: ${field.replace(/_/g, " ")}?`;

  const prompt =
    "Phrase a single, natural, user-facing yes/no-style safety question for a " +
    `home DIY/construction app. The task category is ${JSON.stringify(category)} ` +
    `and the underlying safety field being confirmed is ${JSON.stringify(field)}. ` +
    "Keep it short, plain-language, and specific to that field. Do not state any " +
    "safety fact yourself — only ask the question.";

  const result = await generateStructured(prompt, PhrasedQuestion, "PhrasedQuestion");
  if (result === null || !result.question.trim()) {
    console.warn(
      `LLM follow-up phrasing unavailable for field=${JSON.stringify(field)}; ` +
        `using hardcoded default.`,
    );
    return fallback;
  }

  return result.question.trim();
}

/** Lowercase and collapse whitespace, for substring evidence checking. */
function normalize(text: string): string {
  return (text ?? "").toLowerCase().split(/\s+/).filter(Boolean).join(" ");
}

/**
 * Is `evidence` actually a span of what the user wrote?
 *
 * The check is deliberately mechanical rather than semantic. A prompt
 * instruction not to assume is weak — the previous prompt already said "DO NOT
 * tag a hazard the description does not report" and still produced
 * `work_at_height` for "how do I change my light bulb", because the model
 * inferred bulb → ceiling → overhead → height. Requiring a quote the model
 * cannot produce is what actually closes that path.
 *
 * Whitespace and case are normalised so trivial reformatting does not reject an
 * otherwise-honest quote; nothing else is relaxed.
 */
export function evidenceSupports(description: string, evidence: string): boolean {
  const ev = normalize(evidence);
  if (!ev) return false;
  return normalize(description).includes(ev);
}

/** De-duplicate preserving first-seen order. */
function dedupe(items: string[]): string[] {
  return [...new Set(items)];
}

/**
 * Ask the LLM which hardcoded catalog rules apply. Never trusts the reply.
 *
 * Returns null when the LLM produced no usable reply, and a TagResult otherwise.
 * That distinction is load-bearing: null means "not tagged" (retry later); a
 * TagResult with empty `ruleIds` means "tagged, no hazards apply". convex/jobs.ts
 * persists the difference so a job tagged during an outage is re-tagged rather
 * than permanently treated as hazard-free.
 */
export async function tagHazardsResult(
  description: string,
  category: string,
): Promise<TagResult | null> {
  // The menu carries each rule's full explanation and example wording, not just
  // its one-line summary. Summaries alone are too terse to scope a rule:
  // "Exposed conductors of unverified status" reads as applicable to any job that
  // briefly exposes a wire, so a routine light-fitting swap got tagged with a
  // rule meant for an ACTIVE fault (its keywords are "live wire", "sparking",
  // "arcing", "burning smell") — and that rule has a floor of 5, so every light
  // fitting came back Do-Not-Attempt. Observed live, 2026-07-31. Showing the
  // explanation and the example phrases is what lets the model tell "hazard
  // present" from "hazard conceivable".
  const menu = Object.values(RULES)
    .map(
      (r) =>
        `- id: "${r.id}"\n` +
        `    ${r.summary}\n` +
        `    applies when: ${r.explanation}\n` +
        `    typical wording: ${r.keywords.slice(0, 6).join(", ") || "(no typical wording)"}`,
    )
    .join("\n");

  const questionMenu = [...LLM_SELECTABLE_FOLLOWUP_FIELDS]
    .sort()
    .map((f) => `- field: "${FOLLOWUPS_BY_FIELD[f].field}"\n    asks: ${FOLLOWUPS_BY_FIELD[f].question}`)
    .join("\n");

  const prompt =
    "You are tagging which known hazards apply to a home improvement task, for " +
    "a safety triage system.\n\n" +
    "HAZARDS YOU MAY TAG (choose ONLY from these ids):\n" +
    `${menu}\n\n` +
    "QUESTIONS YOU MAY ASK (choose ONLY from these fields):\n" +
    `${questionMenu}\n\n` +
    "RULES:\n" +
    "1. Do not invent ids or fields. Do not rate severity. Do not assign any " +
    "risk level. Those are decided elsewhere.\n" +
    "2. Every tag MUST quote, in its `evidence` field, the exact words from the " +
    "task description that justify it. Copy them verbatim. A tag whose evidence " +
    "is not found in the description is discarded, so an inferred hazard is the " +
    "same as no hazard.\n" +
    "3. NEVER infer facts the user did not state — not height, not access, not " +
    "condition, not what else might be nearby. If the work is plainly hazardous " +
    "ONLY IF some unstated fact holds, do not tag it: put the matching field in " +
    "`ask` instead. That is what `ask` is for.\n" +
    "4. TAG what is inherent to the work itself, even if the exact word is " +
    "absent: replacing a light FITTING, a ceiling fan or a socket is work on " +
    "fixed wiring. But a consumable that is designed to be user-replaced — a " +
    "light BULB, a filter, a battery, a fuse in a plug — is NOT fixed-wiring " +
    "work. Swapping one is not electrical work on the installation.\n" +
    "5. Do not tag a hazard describing a different location, or a fault the " +
    "description does not report. Work on a fitting is not work on the incoming " +
    "supply or consumer unit. Wiring disconnected during routine work is not a " +
    "live-conductor fault — that is for sparking, arcing or a wire found live, " +
    "which the user would have said.\n\n" +
    `Task category: ${category}\n` +
    `Task description: ${description}\n\n` +
    "Copy ids and fields EXACTLY as written above, character for character — " +
    '"fixed_wiring_work", not "fixed_wiring". A value that is not an exact match ' +
    "is discarded. Return empty lists if nothing applies and nothing needs " +
    "asking.\n\n" +
    `Valid hazard ids: ${[...VALID_RULE_IDS].sort().join(", ")}\n` +
    `Valid question fields: ${[...LLM_SELECTABLE_FOLLOWUP_FIELDS].sort().join(", ")}`;

  const result = await generateStructured(prompt, HazardTags, "HazardTags");
  if (result === null) {
    console.info("tagHazards: no LLM result, falling back to keyword rules only");
    return null;
  }

  const valid: string[] = [];
  const invalid: string[] = [];
  const unsupported: [string, string][] = [];

  for (const tag of result.tags ?? []) {
    if (!VALID_RULE_IDS.has(tag.rule_id)) {
      invalid.push(tag.rule_id);
    } else if (!evidenceSupports(description, tag.evidence)) {
      unsupported.push([tag.rule_id, tag.evidence.slice(0, 80)]);
    } else {
      valid.push(tag.rule_id);
    }
  }

  if (invalid.length > 0) {
    // A model returning ids outside the catalog is a model error, never a new
    // rule. Logged loudly because silent discards hide prompt drift.
    console.warn(
      `tagHazards: discarded ${invalid.length} id(s) outside the hardcoded ` +
        `catalog: ${JSON.stringify(invalid)}`,
    );
  }
  if (unsupported.length > 0) {
    // The model asserted a hazard it could not quote the user on. Logged at
    // warning because a rising rate here means the prompt is drifting back
    // toward inference.
    console.warn(
      `tagHazards: discarded ${unsupported.length} ungrounded tag(s) (evidence ` +
        `not found in the description): ${JSON.stringify(unsupported)}`,
    );
  }

  const askValid = (result.ask ?? []).filter((f) => LLM_SELECTABLE_FOLLOWUP_FIELDS.has(f));
  const askInvalid = (result.ask ?? []).filter((f) => !LLM_SELECTABLE_FOLLOWUP_FIELDS.has(f));
  if (askInvalid.length > 0) {
    console.warn(
      `tagHazards: discarded ${askInvalid.length} follow-up field(s) outside the ` +
        `selectable set: ${JSON.stringify(askInvalid)}`,
    );
  }

  return { ruleIds: dedupe(valid), askFields: dedupe(askValid) };
}

/**
 * `tagHazardsResult`, flattened to just the rule ids.
 *
 * Callers that need to tell "the LLM was down" apart from "it ran and found no
 * hazards" must use `tagHazardsResult` — the two cases are indistinguishable
 * here, and conflating them would let a job cache an empty hazard set produced
 * by an outage.
 */
export async function tagHazards(description: string, category: string): Promise<string[]> {
  const result = await tagHazardsResult(description, category);
  return result === null ? [] : [...result.ruleIds];
}
