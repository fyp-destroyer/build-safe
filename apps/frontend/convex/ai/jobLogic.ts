/**
 * Pure job logic shared by the Convex queries, mutations and actions.
 *
 * Ported from apps/backend/services/job_service.py. Everything here is a pure
 * function of a job document — no database, no network — so the follow-up GATE
 * and the follow-up SCORER can be the same code called from both a mutation and
 * an action. Keeping them as one function is not tidiness: two copies of a
 * safety-critical mapping is exactly the kind of thing that goes stale silently,
 * and this codebase has already been bitten by it once.
 */

import { requiredFollowups, type FollowupAnswers } from "./ruleEngine/rules";

/** The subset of a job document this module needs. */
export interface JobLike {
  description: string;
  category: string;
  followupAnswers: FollowupAnswers;
  llmHazardIds?: string[] | null;
  llmFollowupFields?: string[] | null;
}

/**
 * The LLM-proposed catalog rule ids resolved for this job, or [].
 *
 * Read from the persisted field, NEVER re-derived. The follow-up gate, the
 * question shown to the user, and the escalation at assessment all read this one
 * value, so they cannot disagree about which hazards apply.
 *
 * They used to disagree: tagging ran only inside assessment, while the gate
 * matched keywords alone. "replace my ceiling fans" matches no keyword, so no
 * follow-up was required and none was asked — then the tagger flagged
 * `fixed_wiring_work` at assessment, which made `power_isolated` required,
 * unanswered, and worth a level-5 floor. The user was told a safety-critical
 * question went unanswered without ever having been shown one. Rules may only
 * escalate on facts the user had a chance to supply.
 *
 * A null value means tagging never succeeded (the LLM was down at creation); the
 * job degrades to keyword-only hazards, which is the documented no-LLM
 * behaviour, and `ensureHazardIds` retries later.
 */
export function hazardIds(job: JobLike): string[] {
  return job.llmHazardIds ?? [];
}

/**
 * Follow-up fields the tagger asked for, or [].
 *
 * Read from the persisted field for the same reason as `hazardIds`: the
 * questions the user is shown and the fields assessment scores against must be
 * one set, not two derivations that can disagree. Unioned with the
 * catalog-derived fields inside `requiredFollowups`, never subtracted — the LLM
 * widens the question set and can never narrow it.
 */
export function askedFields(job: JobLike): string[] {
  return job.llmFollowupFields ?? [];
}

/**
 * Fields that still need an answer at all (key absent), not fields whose answer
 * happens to be the unsafe one.
 *
 * "Missing" here means UNRESOLVED: unresolved fields block assessment. An
 * *answered* field — even an explicit `false`, i.e. the user confirming the
 * unsafe condition — is resolved and must be allowed through to assessment,
 * where the rule engine's own falsy-answer check (a distinct, correct concern)
 * is what escalates risk for it.
 *
 * Gating on truthiness here would make that escalation path unreachable: a job
 * could never be assessed once a safety-critical answer was honestly "no",
 * permanently blocking instead of ever producing the Dangerous / Do-Not-Attempt
 * result the rule engine is designed to compute for exactly that case.
 */
export function missingRequiredFollowups(job: JobLike): string[] {
  const required = requiredFollowups({
    description: job.description,
    category: job.category,
    llmHazardIds: hazardIds(job),
    followupAnswers: job.followupAnswers,
    llmAskedFields: askedFields(job),
  });
  return required.filter((field) => !(field in job.followupAnswers));
}

/**
 * The status a job should have given its current answers.
 *
 * Applied identically at creation and after every answer, so `status` is
 * trustworthy immediately rather than only becoming accurate after the first
 * update. A category with zero required fields would otherwise sit at
 * "pending_followup" with nothing left to ask — a real, observed inconsistency
 * between the two signals.
 */
export function statusFor(job: JobLike): "pending_followup" | "ready_to_assess" {
  return missingRequiredFollowups(job).length > 0 ? "pending_followup" : "ready_to_assess";
}

/**
 * The first still-missing required field, chosen deterministically.
 *
 * Sorted so behaviour is stable regardless of iteration order. This never
 * decides WHICH fields are required — that is the hardcoded catalog's job — it
 * only picks one among the already-known-missing ones to ask about next.
 */
export function nextMissingField(job: JobLike): string | null {
  const missing = missingRequiredFollowups(job);
  if (missing.length === 0) return null;
  return [...missing].sort()[0];
}

/**
 * Templated explanation text — facts inserted, never freely generated
 * (rules.md §4 point 3).
 *
 * The text must describe the pipeline that ACTUALLY RAN. When the classifier is
 * not contributing, it must not be cited as a reason: telling a user "Classifier
 * predicted 4" for a number the classifier had no part in is a false explanation
 * of a safety decision, which is worse than a terse one.
 */
export function buildExplanation(
  mlRisk: number | null,
  ruleRisk: number,
  finalRisk: number,
  triggeredRules: string[],
  useMl: boolean,
): string {
  const ruleList = triggeredRules.join(", ");

  if (!useMl || mlRisk === null) {
    if (triggeredRules.length === 0) {
      return `No safety rules were triggered for this task. Final risk level: ${finalRisk}.`;
    }
    return `The following safety rules were triggered: ${ruleList}. Final risk level: ${finalRisk}.`;
  }

  if (triggeredRules.length === 0) {
    return (
      `Classifier predicted risk level ${mlRisk}. No safety rules were ` +
      `triggered. Final risk level: ${finalRisk}.`
    );
  }
  return (
    `Classifier predicted risk level ${mlRisk}. The following safety rules were ` +
    `triggered: ${ruleList} (rule engine risk level ${ruleRisk}). Final risk ` +
    `level is the higher of the two: ${finalRisk}.`
  );
}

/**
 * Whether the ML classifier contributes to the decision.
 *
 * Named `mlClassifierEnabled` rather than `useMlClassifier` purely because the
 * `use` prefix makes ESLint's rules-of-hooks treat it as a React hook.
 *
 * Defaults to TRUE — the documented pipeline (`finalRisk = max(ML, rules)`) is
 * the code's default, and only an explicit "false" turns it off. Removing a term
 * from a max() can only lower the result, so disabling this is strictly a
 * reduction in escalation and must be a deliberate act.
 */
export function mlClassifierEnabled(): boolean {
  const raw = (process.env.RISK_USE_ML_CLASSIFIER ?? "true").trim().toLowerCase();
  return !["false", "0", "no", "off"].includes(raw);
}
