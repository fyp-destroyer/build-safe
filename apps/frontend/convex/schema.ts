/**
 * Convex schema — port of the five PostgreSQL tables this app used to run on
 * (apps/backend/models/). Convex's built-in `_id` and `_creationTime` replace
 * the old `id` UUID and `created_at` columns everywhere, so neither is
 * declared below.
 *
 * Two fields are deliberately NOT carried over: `skill_level` and `urgency`.
 * Both were retired from the product (2026-08-02 and 2026-07-31) and survived
 * in Postgres only as nullable columns kept for reversibility. A fresh
 * database is the right moment to stop carrying them.
 */

import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

/** The 9 categories locked in phases.md Phase 1 (was schemas/job.py TASK_CATEGORIES). */
export const taskCategory = v.union(
  v.literal("electrical"),
  v.literal("plumbing"),
  v.literal("carpentry"),
  v.literal("masonry"),
  v.literal("painting"),
  v.literal("tiling"),
  v.literal("hvac"),
  v.literal("roofing"),
  v.literal("general"),
);

/** What a user may answer to a safety-critical follow-up. See jobs.followupAnswers. */
export const followupAnswer = v.union(v.boolean(), v.literal("unsure"));

export const jobStatus = v.union(
  v.literal("pending_followup"),
  v.literal("ready_to_assess"),
  v.literal("assessed"),
  v.literal("failed"),
);

export default defineSchema({
  /**
   * A user, keyed by Clerk's subject claim. Created just-in-time on the first
   * authenticated call (see convex/users.ts) rather than by a Clerk webhook —
   * the webhook-based sync sketched in phases.md:107 exists to keep a local
   * row as an FK target, and JIT creation achieves that with no extra moving
   * part and no window where a signed-in user has no row.
   */
  users: defineTable({
    clerkUserId: v.string(),
    email: v.string(),
    name: v.string(),
  }).index("by_clerk_id", ["clerkUserId"]),

  jobs: defineTable({
    userId: v.id("users"),
    description: v.string(),
    category: taskCategory,
    /**
     * Answers keyed by follow-up field name.
     *
     * THREE values, not two: `true` (safe condition holds), `false` (it does
     * not), and `"unsure"` (the user does not know). A yes/no question forces
     * someone who has not checked to claim something either way, and both
     * claims are wrong in ways that matter — so "unsure" is stored as itself
     * rather than folded into "no". It escalates as hard as no answer at all.
     *
     * A field being ABSENT remains distinct from all three.
     */
    followupAnswers: v.record(v.string(), followupAnswer),
    /**
     * Hazard ids tagged by the LLM once at creation.
     *
     * `null` means NEVER TAGGED; `[]` means tagged and nothing matched. That
     * distinction is load-bearing, not stylistic: deriving hazards twice (once
     * to decide what to ask, once to score) let the two derivations drift and
     * produced the phantom follow-up penalty bug. Persisting once at creation
     * is the fix, and it only works if "no tags yet" and "no tags found" stay
     * distinguishable.
     *
     * `undefined` (field absent) is treated identically to `null`.
     */
    llmHazardIds: v.optional(v.union(v.null(), v.array(v.string()))),
    /** Safety-critical follow-up field names the LLM judged relevant, if tagged. */
    llmFollowupFields: v.optional(v.union(v.null(), v.array(v.string()))),
    /**
     * The next still-unanswered safety-critical follow-up, with its wording.
     *
     * The Python backend computed this per request and never stored it. Here it
     * is persisted, because phrasing the question is an LLM call and Convex
     * queries cannot do network I/O — a query must be a pure function of the
     * database. It is recomputed by whichever action last changed the answers,
     * so it cannot go stale.
     *
     * WHICH field is required is still decided entirely by the hardcoded
     * catalog; only the WORDING comes from the LLM, and that has a hardcoded
     * fallback (rules.md §4).
     */
    nextFollowup: v.optional(
      v.union(v.null(), v.object({ field: v.string(), question: v.string() })),
    ),
    status: jobStatus,
  }).index("by_user", ["userId"]),

  /**
   * At most ONE per job. Postgres enforced this with a unique constraint on
   * job_id; Convex has no unique indexes, so assessments.record must
   * check-then-insert. That is race-free because Convex mutations are
   * transactional.
   */
  riskAssessments: defineTable({
    jobId: v.id("jobs"),
    riskLevel: v.number(), // 1-5
    confidence: v.number(),
    explanation: v.string(),
    hazardTags: v.array(v.string()),
    triggeredRules: v.array(v.string()),
    cost: v.optional(v.union(v.null(), v.string())),
    time: v.optional(v.union(v.null(), v.string())),
    difficulty: v.optional(v.union(v.null(), v.string())),
    status: v.union(v.literal("completed"), v.literal("failed")),
  }).index("by_job", ["jobId"]),

  /**
   * Written on EVERY assessment attempt including failures, with no sampling
   * (rules.md §4.6). Deleted with its job — those rows embed the task
   * description, so keeping them after a user deletes the conversation would
   * retain exactly the data they asked to be rid of.
   */
  aiLogs: defineTable({
    jobId: v.id("jobs"),
    modelInput: v.any(),
    modelOutput: v.any(),
    triggeredRules: v.array(v.string()),
  }).index("by_job", ["jobId"]),

  /**
   * The conversation transcript.
   *
   * A `kind: "risk_card"` row stores NO VERDICT — no risk level, no hazards,
   * no explanation, and `text` must be null. It marks only where the card
   * belongs in the conversation; the card itself is re-rendered from
   * riskAssessments at read time. A second copy of a verdict could drift from
   * the assessment of record and show the user a stale risk level as current,
   * so there is exactly one place a risk level lives and the transcript points
   * at it instead of duplicating it.
   *
   * `userId` is denormalised alongside `jobId` so ownership checks skip a join.
   */
  chatMessages: defineTable({
    userId: v.id("users"),
    jobId: v.id("jobs"),
    role: v.union(v.literal("user"), v.literal("assistant")),
    kind: v.union(v.literal("text"), v.literal("risk_card")),
    text: v.optional(v.union(v.null(), v.string())),
    /**
     * Explicit ordering. A batch of messages is written in one transaction and
     * _creationTime can tie at that resolution, which would let a transcript
     * render out of order — the one thing storing it must get right.
     */
    position: v.number(),
  }).index("by_job", ["jobId"]),
});
