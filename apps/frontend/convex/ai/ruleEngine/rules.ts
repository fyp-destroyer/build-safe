/**
 * Deterministic safety rule engine.
 *
 * Evaluates a job's context against the hardcoded catalog in `catalog.ts` and
 * returns an escalation floor. This module contains the LOGIC; `catalog.ts`
 * holds the DATA. No hazard may be defined anywhere else.
 *
 * Ported from apps/backend/ai/rule_engine/rules.py. The Python and TypeScript
 * engines were verified to produce identical (risk, triggeredRules) output for
 * every row of the 555-row dataset and the 24-case pre-committed holdout before
 * the Python original was removed — see tools/compare_rule_engines.py.
 *
 * THE ONE INVARIANT THIS MODULE MUST NEVER BREAK
 * ----------------------------------------------
 * Rules only ever escalate. `evaluate()` returns a floor derived purely from
 * matched rules, defaulting to MIN_RISK_LEVEL when nothing matches; it has no
 * code path that lowers anything. Callers compute:
 *
 *     finalRisk = max(mlRisk, ruleRisk)
 *
 * so a rule can raise a low ML prediction but can never pull a high one down
 * (rules.md §4.2, srs.md §8.1, NFR-03).
 *
 * WHAT THE LLM MAY AND MAY NOT DO HERE
 * ------------------------------------
 * `llmAssist.tagHazards()` may propose which EXISTING catalog rule ids apply to
 * a free-text description, and which EXISTING follow-up fields to ask about when
 * the description is ambiguous. That is the whole of its authority. It cannot
 * invent a rule or a question, cannot set or suggest a risk number, and cannot
 * change a floor. Every id it returns is filtered against `VALID_RULE_IDS` (or
 * `LLM_SELECTABLE_FOLLOWUP_FIELDS`) and then held to the same catalog conditions
 * a keyword match must satisfy, so a hallucinated or out-of-scope id is
 * discarded (rules.md §4.1). LLM contributions are additive only: they can cause
 * a rule to fire that keywords missed, never suppress one that matched.
 *
 * GATES ARE NOT DE-ESCALATION
 * ---------------------------
 * `Rule.gatedBy` lets a confirmed-safe user answer stop a rule from firing.
 * Nothing is lowered by this: the rule never fires, so no risk level is ever
 * reduced, and an UNANSWERED gate still fires the rule at its full floor. It is
 * `excludes` sourced from an answer instead of from text. The invariant that
 * `evaluate()` has no path which lowers anything still holds exactly.
 */

import {
  FOLLOWUPS,
  FOLLOWUPS_BY_FIELD,
  LLM_SELECTABLE_FOLLOWUP_FIELDS,
  MAX_RISK_LEVEL,
  MIN_RISK_LEVEL,
  RULES,
  VALID_RULE_IDS,
  type Rule,
} from "./catalog";

export { MIN_RISK_LEVEL, MAX_RISK_LEVEL };

/** Answers to safety-critical follow-ups. A field being ABSENT and a field
 *  being `false` are different states — see `nextFollowup` and `evaluate`. */
export type FollowupAnswers = Record<string, boolean | undefined>;

/**
 * Every applicability condition on `rule` EXCEPT its keywords.
 *
 * Split out of `matches` so the LLM tagging path can be held to the same
 * conditions as the keyword path. It previously was not: an LLM-proposed id was
 * checked for membership in the catalog and nothing else, so it bypassed
 * `excludes`, `categories` and `requiresSkill` entirely. `work_at_height` lists
 * "step ladder" and "ground level" in its excludes and an LLM tag ignored both.
 * The docstring promised these vetoes applied; for half the ways a rule could
 * fire, they did not.
 *
 * Keywords stay OUT of this check on purpose — catching hazards that keyword
 * matching missed is the entire point of LLM tagging.
 */
function gatesAllow(
  rule: Rule,
  text: string,
  category: string,
  skill: string,
  answers: FollowupAnswers,
): boolean {
  if (rule.categories.length > 0 && !rule.categories.includes(category)) return false;
  if (rule.requiresSkill.length > 0 && !rule.requiresSkill.includes(skill)) return false;
  if (rule.excludes.some((x) => text.includes(x))) return false;
  // A gate closes only on an explicit confirmed-safe answer. Missing or false
  // leaves the rule firing — silence must never buy a lower risk level.
  if (rule.gatedBy.some((f) => answers[f] === true)) return false;
  return true;
}

function matches(
  rule: Rule,
  text: string,
  category: string,
  skill: string,
  answers: FollowupAnswers,
): boolean {
  if (!gatesAllow(rule, text, category, skill, answers)) return false;
  return rule.keywords.some((k) => text.includes(k));
}

/** De-duplicate preserving first-seen order (two keywords can map to one rule). */
function dedupe(items: string[]): string[] {
  return [...new Set(items)];
}

export interface RuleEngineInput {
  description: string;
  category: string;
  llmHazardIds?: readonly string[] | null;
  userSkill?: string | null;
  followupAnswers?: FollowupAnswers | null;
  llmAskedFields?: readonly string[] | null;
}

/**
 * Which catalog rules fire for this job, keyword and LLM paths combined.
 *
 * The LLM contribution is filtered against the closed catalog first. Any id
 * outside it is dropped — it is a model error, never a new rule. It is then held
 * to the same `excludes` / `categories` / `requiresSkill` / `gatedBy` conditions
 * as a keyword match, so an LLM tag can only cause a rule to fire in
 * circumstances where the catalog says that rule applies.
 *
 * Tagging remains ADDITIVE: a keyword match is evaluated independently and is
 * never suppressed by anything the LLM did or did not return.
 */
export function matchedRuleIds(input: RuleEngineInput): string[] {
  const { description, category, llmHazardIds, userSkill, followupAnswers } = input;

  const text = `${description} ${category}`.toLowerCase();
  const cat = (category ?? "").toLowerCase();
  const skill = (userSkill ?? "").trim().toLowerCase();
  const answers = followupAnswers ?? {};

  const fired = Object.values(RULES)
    .filter((r) => matches(r, text, cat, skill, answers))
    .map((r) => r.id);

  if (llmHazardIds && llmHazardIds.length > 0) {
    const unknown = llmHazardIds.filter((i) => !VALID_RULE_IDS.has(i));
    if (unknown.length > 0) {
      console.warn(
        `rule_engine: discarding ${unknown.length} LLM-proposed rule id(s) outside ` +
          `the hardcoded catalog: ${JSON.stringify(unknown)}`,
      );
    }
    const vetoed = llmHazardIds.filter(
      (i) => VALID_RULE_IDS.has(i) && !gatesAllow(RULES[i], text, cat, skill, answers),
    );
    if (vetoed.length > 0) {
      console.info(
        `rule_engine: ${vetoed.length} LLM-proposed rule id(s) vetoed by catalog ` +
          `conditions (excludes/category/skill/gate): ${JSON.stringify(vetoed)}`,
      );
    }
    for (const i of llmHazardIds) {
      if (VALID_RULE_IDS.has(i) && gatesAllow(RULES[i], text, cat, skill, answers)) {
        fired.push(i);
      }
    }
  }

  return dedupe(fired);
}

/**
 * Safety-critical follow-up fields that apply to this job.
 *
 * Driven by which hazard rules fired, not by category alone: a task can need
 * `power_isolated` without being category `electrical` (chasing a wall before
 * tiling, wiring a thermostat). Category is a fallback trigger only.
 *
 * `llmAskedFields` are fields the tagger asked for because the description was
 * ambiguous about them. They are unioned in, never subtracted: the LLM can widen
 * the question set but cannot narrow the one the catalog derived. Ids outside the
 * closed selectable set are dropped.
 */
export function requiredFollowups(input: RuleEngineInput): string[] {
  const fired = new Set(matchedRuleIds(input));
  const cat = (input.category ?? "").toLowerCase();
  const asked = input.llmAskedFields ?? [];

  const out: string[] = [];
  for (const f of FOLLOWUPS) {
    const byRule = f.appliesWhenRule.some((r) => fired.has(r));
    const byCategory = f.appliesToCategories.includes(cat);
    const byLlm = asked.includes(f.field) && LLM_SELECTABLE_FOLLOWUP_FIELDS.has(f.field);
    if (byRule || byCategory || byLlm) out.push(f.field);
  }
  return out;
}

/**
 * The next unanswered safety-critical field, or null if all are answered.
 *
 * Presence, not truthiness: an explicit `false` is an ANSWER (the user said
 * "no"), and must not be re-asked forever. Conflating the two once made the
 * entire dangerous-task path unreachable — see memory.md, 2026-07-19.
 */
export function nextFollowup(input: RuleEngineInput): string | null {
  const answers = input.followupAnswers ?? {};
  for (const f of requiredFollowups(input)) {
    if (!(f in answers)) return f;
  }
  return null;
}

export interface RuleEngineResult {
  risk: number;
  triggered: string[];
}

/**
 * Return the rule-derived risk floor and the rule names that produced it.
 *
 * `risk` is always within [MIN_RISK_LEVEL, MAX_RISK_LEVEL] and defaults to
 * MIN_RISK_LEVEL when nothing matches. This function never lowers anything — it
 * proposes an escalation floor and nothing more.
 */
export function evaluate(input: RuleEngineInput): RuleEngineResult {
  const answers = input.followupAnswers ?? {};
  const triggered: string[] = [];
  let risk = MIN_RISK_LEVEL;

  for (const ruleId of matchedRuleIds(input)) {
    triggered.push(ruleId);
    risk = Math.max(risk, RULES[ruleId].floor);
  }

  // Safety-critical follow-ups. Missing and denied are DIFFERENT states and
  // escalate differently; see catalog.FOLLOWUPS for why missing scores higher
  // than an explicit "no".
  for (const field of requiredFollowups(input)) {
    const spec = FOLLOWUPS_BY_FIELD[field];
    if (!(field in answers)) {
      triggered.push(`missing_followup:${field}`);
      risk = Math.max(risk, spec.floorWhenMissing);
    } else if (answers[field] === false) {
      triggered.push(`unsafe_followup:${field}`);
      risk = Math.max(risk, spec.floorWhenDenied);
    }
  }

  risk = Math.min(Math.max(risk, MIN_RISK_LEVEL), MAX_RISK_LEVEL);
  return { risk, triggered: dedupe(triggered) };
}

/**
 * Templated, hardcoded explanation text for triggered rules.
 *
 * Deliberately templated rather than LLM-generated: rules.md §4 permits the LLM
 * to phrase explanations, but the safety content itself is fixed here so it
 * cannot drift or be hallucinated. Unknown ids are skipped rather than guessed at.
 */
export function explain(triggered: readonly string[]): string[] {
  const out: string[] = [];
  for (const name of triggered) {
    if (name.startsWith("missing_followup:")) {
      const field = name.slice("missing_followup:".length);
      const spec = FOLLOWUPS_BY_FIELD[field];
      if (spec) {
        out.push(
          `A safety-critical question was not answered ("${spec.question}"). ` +
            `Because that cannot be ruled out, this task is treated as the worst ` +
            `plausible case.`,
        );
      }
    } else if (name.startsWith("unsafe_followup:")) {
      const field = name.slice("unsafe_followup:".length);
      const spec = FOLLOWUPS_BY_FIELD[field];
      if (spec) {
        out.push(
          `You indicated a safety-critical condition is not met ("${spec.question}" ` +
            `— answered no), which raises the risk of this task.`,
        );
      }
    } else if (name in RULES) {
      out.push(RULES[name].explanation);
    }
  }
  return out;
}
