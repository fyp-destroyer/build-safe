/**
 * Risk assessment: classifier + rule engine → finalRisk = max(ML, rules).
 *
 * Ported from apps/backend/services/job_service.py `assess_job`.
 *
 * THE NON-NEGOTIABLE INVARIANT
 * ----------------------------
 *     finalRisk = max(mlRisk, ruleRisk)
 *
 * The rule engine only ever proposes an escalation FLOOR, so a rule can raise a
 * low ML prediction but can never pull a high one down (rules.md §4.2, srs.md
 * §8.1 NFR-03). Both halves were verified identical to the Python originals over
 * the whole dataset before that code was removed — see tools/compare_*.mjs.
 *
 * FAIL LOUD, NEVER "SAFE"
 * -----------------------
 * On any exception inside the AI pipeline, the assessment is written with
 * status "failed" and the DIY recommendation is blocked. There is no path that
 * silently substitutes a safe-looking result. An aiLogs row is written on EVERY
 * attempt including failures, with no sampling (rules.md §4.6).
 */

import { v } from "convex/values";
import { action, internalMutation, query } from "./_generated/server";
import { internal } from "./_generated/api";
import { getUserForRead } from "./users";
import { ensureHazardIds } from "./jobs";
import { classify } from "./ai/classifier/classify";
import { evaluate, explain } from "./ai/ruleEngine/rules";
import {
  askedFields,
  buildExplanation,
  hazardIds,
  missingRequiredFollowups,
  mlClassifierEnabled,
} from "./ai/jobLogic";

/**
 * Plain-language guidance for each triggered rule, derived at READ time from the
 * hardcoded catalog.
 *
 * Never stored. Storing it would create a second copy of safety text that could
 * drift from the catalog, and the catalog is the single source of truth.
 */
function safetyNotes(triggeredRules: string[]): string[] {
  return explain(triggeredRules);
}

/** The full assessment for a job, or null if there is none / not the caller's. */
export const get = query({
  args: { jobId: v.id("jobs") },
  handler: async (ctx, args) => {
    const user = await getUserForRead(ctx);
    if (user === null) return null;
    const job = await ctx.db.get(args.jobId);
    if (job === null || job.userId !== user._id) return null;

    const assessment = await ctx.db
      .query("riskAssessments")
      .withIndex("by_job", (q) => q.eq("jobId", args.jobId))
      .unique();

    if (assessment === null) return null;

    return {
      ...assessment,
      // Derived, never persisted — see safetyNotes above.
      safetyNotes: safetyNotes(assessment.triggeredRules),
    };
  },
});

/**
 * Write the assessment and its audit log in ONE transaction.
 *
 * Postgres enforced one-assessment-per-job with a unique constraint on job_id.
 * Convex has no unique indexes, so the check happens here — race-free because
 * mutations are transactional.
 */
export const record = internalMutation({
  args: {
    jobId: v.id("jobs"),
    riskLevel: v.number(),
    confidence: v.number(),
    explanation: v.string(),
    hazardTags: v.array(v.string()),
    triggeredRules: v.array(v.string()),
    status: v.union(v.literal("completed"), v.literal("failed")),
    modelInput: v.any(),
    modelOutput: v.any(),
  },
  handler: async (ctx, args) => {
    const { jobId, modelInput, modelOutput, ...assessment } = args;

    // Every attempt is logged, including failures. No sampling (rules.md §4.6).
    await ctx.db.insert("aiLogs", {
      jobId,
      modelInput,
      modelOutput,
      triggeredRules: args.triggeredRules,
    });

    const existing = await ctx.db
      .query("riskAssessments")
      .withIndex("by_job", (q) => q.eq("jobId", jobId))
      .unique();

    if (existing !== null) {
      // One chat = one job = one assessment. Re-assessment overwrites rather
      // than accumulating, so there is never more than one verdict of record.
      await ctx.db.patch(existing._id, assessment);
    } else {
      await ctx.db.insert("riskAssessments", { jobId, ...assessment });
    }

    await ctx.db.patch(jobId, { status: args.status === "failed" ? "failed" : "assessed" });
  },
});

/**
 * Run the assessment pipeline for a job.
 *
 * An action because the classifier and the rule engine are pure but
 * `ensureHazardIds` may call the LLM. The risk arithmetic itself never touches
 * the network.
 */
export const assess = action({
  args: { jobId: v.id("jobs") },
  handler: async (ctx, args): Promise<{ status: string; riskLevel: number | null }> => {
    // Confirm ownership before doing any work, and fail the same way for a
    // missing job as for someone else's.
    const owned = await ctx.runQuery(internal.jobs.getInternal, { jobId: args.jobId });
    const identity = await ctx.auth.getUserIdentity();
    if (identity === null) throw new Error("Not authenticated");
    if (owned === null) throw new Error("No job found with that id.");

    // Last chance to tag if creation-time tagging failed. Must run BEFORE the
    // gate: a hazard discovered here may add a follow-up, and the correct
    // response is to send the user back to answer it, never to assess and
    // escalate on a field they were never shown.
    await ensureHazardIds(ctx, args.jobId);

    const job = await ctx.runQuery(internal.jobs.getInternal, { jobId: args.jobId });
    if (job === null) throw new Error("No job found with that id.");

    if (missingRequiredFollowups(job).length > 0) {
      throw new Error(
        "Safety-critical follow-up questions must be answered before assessment.",
      );
    }

    const modelInput = {
      description: job.description,
      category: job.category,
      followupAnswers: job.followupAnswers,
    };

    const useMl = mlClassifierEnabled();

    try {
      // The classifier runs either way, so its prediction is always on record in
      // aiLogs and a broken model is always visible. Only its CONTRIBUTION to
      // the decision is gated.
      let mlRisk: number | null = null;
      let confidence = 0;
      let mlError: string | null = null;

      try {
        const result = classify(job.description, job.category);
        mlRisk = result.riskLevel;
        confidence = result.confidence;
      } catch (exc) {
        if (useMl) {
          // The documented pipeline depends on this number; failing to get it
          // must fail the assessment, never default to "safe".
          throw exc;
        }
        // Rules-only mode: the classifier has no say, so its failure cannot make
        // the result wrong. Recorded rather than swallowed.
        console.warn(`classifier unavailable (rules-only mode active): ${exc}`);
        mlError = `${(exc as Error).name}: ${(exc as Error).message}`;
      }

      // Read the tags from the job rather than re-tagging: the gate above must
      // have been evaluated against the SAME ids, or assessment can escalate on
      // a hazard whose follow-up was never asked. Empty means keyword rules
      // alone still run — the engine degrades to "no LLM", never to "no hazards".
      const { risk: ruleRisk, triggered: triggeredRules } = evaluate({
        description: job.description,
        category: job.category,
        followupAnswers: job.followupAnswers,
        llmHazardIds: hazardIds(job),
        llmAskedFields: askedFields(job),
      });

      // THE non-negotiable invariant: rules only ever escalate.
      const finalRisk = useMl && mlRisk !== null ? Math.max(mlRisk, ruleRisk) : ruleRisk;
      if (!(finalRisk >= 1 && finalRisk <= 5)) {
        throw new Error(`finalRisk out of bounds: ${finalRisk}`);
      }

      const modelOutput: Record<string, unknown> = {
        mlRisk,
        mlConfidence: confidence,
        ruleRisk,
        finalRisk,
        // Explicit, not inferred: a future reader of aiLogs must be able to tell
        // "the classifier agreed" from "the classifier was not consulted", which
        // mlRisk alone cannot express.
        mlUsed: useMl,
      };
      if (mlError) modelOutput.mlError = mlError;

      await ctx.runMutation(internal.assessments.record, {
        jobId: args.jobId,
        riskLevel: finalRisk,
        confidence,
        explanation: buildExplanation(mlRisk, ruleRisk, finalRisk, triggeredRules, useMl),
        // Hazards only. A `safe_followup:` marker records a precaution the user
        // CONFIRMED, so listing it among hazard tags would present the user's
        // own safety measure back to them as a danger. It stays in
        // `triggeredRules`, which is the full audit trail.
        hazardTags: triggeredRules.filter((r) => !r.startsWith("safe_followup:")),
        triggeredRules,
        status: "completed",
        modelInput,
        modelOutput,
      });

      return { status: "completed", riskLevel: finalRisk };
    } catch (exc) {
      console.error(`AI pipeline failure during assess for job ${args.jobId}:`, exc);

      await ctx.runMutation(internal.assessments.record, {
        jobId: args.jobId,
        // Worst plausible case placeholder; status "failed" blocks display.
        riskLevel: 5,
        confidence: 0,
        explanation: "Risk assessment failed. This task must not be treated as safe.",
        hazardTags: [],
        triggeredRules: [],
        status: "failed",
        modelInput,
        modelOutput: {
          error: String((exc as Error).message ?? exc),
          errorType: (exc as Error).name ?? "Error",
        },
      });

      return { status: "failed", riskLevel: null };
    }
  },
});
