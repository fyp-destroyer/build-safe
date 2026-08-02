/**
 * Placeholder tool/material/PPE recommendation, gated on risk level.
 *
 * Ported from apps/backend/services/recommendation_service.py, including its
 * honesty: the real catalog-backed engine was never implemented, and every
 * response is flagged `isPlaceholder: true` so the gap is visible in the API
 * rather than only in a doc. Every task gets the same generic items — this
 * proves the endpoint shape and the risk gating, nothing more.
 */

import { v } from "convex/values";
import { query } from "./_generated/server";
import { getUserForRead } from "./users";

interface RecommendedItem {
  name: string;
  category: string;
  required: boolean;
  note: string;
}

const PLACEHOLDER_NOTE = "Placeholder recommendation — real catalog not implemented (Phase 6).";

/** Fixed placeholder list, gated only on riskLevel. Not a real catalog lookup. */
function placeholderItems(riskLevel: number): RecommendedItem[] {
  const items: RecommendedItem[] = [
    {
      name: "Safety glasses",
      category: "ppe",
      required: riskLevel >= 2,
      note: PLACEHOLDER_NOTE,
    },
    {
      name: "Work gloves",
      category: "ppe",
      required: riskLevel >= 2,
      note: PLACEHOLDER_NOTE,
    },
  ];

  if (riskLevel >= 3) {
    items.push({
      name: "Licensed professional consultation",
      category: "service",
      required: true,
      note: "Risk level indicates this task should involve a professional.",
    });
  }
  if (riskLevel >= 4) {
    items.push({
      name: "Do not proceed without professional isolation/inspection",
      category: "warning",
      required: true,
      note: "Placeholder — real guidance text is templated from ai/explanation in a later phase.",
    });
  }
  return items;
}

/**
 * Recommendations for a job's COMPLETED assessment.
 *
 * Returns null when there is no completed assessment. A failed assessment gets
 * nothing: recommending PPE for a task whose risk could not be established would
 * imply the task is approachable, which is exactly the silent "safe" fallback
 * rules.md §2 forbids.
 */
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

    if (assessment === null || assessment.status !== "completed") return null;

    return {
      jobId: args.jobId,
      riskLevel: assessment.riskLevel,
      items: placeholderItems(assessment.riskLevel),
      isPlaceholder: true,
    };
  },
});
