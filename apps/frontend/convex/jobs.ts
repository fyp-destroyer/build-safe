/**
 * Job lifecycle: create, list, answer follow-ups, delete.
 *
 * Ported from apps/backend/routers/jobs.py + services/job_service.py.
 *
 * WHY SOME OF THESE ARE ACTIONS
 * -----------------------------
 * Creating a job and answering a follow-up both need the LLM (category tagging,
 * hazard tagging, question phrasing), and network I/O is only legal in a Convex
 * action. So each is an action that does its LLM work first and then commits
 * through an internal mutation. That split is a feature, not a workaround: it
 * makes it structurally impossible for the transactional, risk-bearing code to
 * call a model.
 *
 * OWNERSHIP IS 404, NEVER 403
 * ---------------------------
 * `getOwnedJob` throws the same "not found" whether a job does not exist or
 * belongs to somebody else. Distinguishing them would confirm the existence of
 * another user's data to anyone who guessed an id.
 */

import { v } from "convex/values";
import { action, internalMutation, internalQuery, mutation, query } from "./_generated/server";
import { internal } from "./_generated/api";
import type { Doc, Id } from "./_generated/dataModel";
import type { ActionCtx, MutationCtx, QueryCtx } from "./_generated/server";
import { taskCategory, followupAnswer } from "./schema";
import { requireUser, getUserForRead, deleteJobChildren } from "./users";
import { statusFor, nextMissingField, type JobLike } from "./ai/jobLogic";
import {
  phraseFollowupQuestion,
  tagCategory,
  tagHazardsResult,
  TASK_CATEGORIES,
} from "./ai/ruleEngine/llmAssist";

/**
 * Fetch a job, throwing if it is missing OR not owned by the caller.
 *
 * Identical error either way — never leak the existence of another user's job.
 */
export async function getOwnedJob(
  ctx: QueryCtx,
  jobId: Id<"jobs">,
  userId: Id<"users">,
): Promise<Doc<"jobs">> {
  const job = await ctx.db.get(jobId);
  if (job === null || job.userId !== userId) {
    throw new Error("No job found with that id.");
  }
  return job;
}

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

/** The caller's jobs, most recent first (the sidebar history). */
export const list = query({
  args: {},
  handler: async (ctx) => {
    // Read path: a signed-in user whose row has not been created yet simply has
    // no jobs, so return an empty list rather than erroring the whole sidebar.
    const user = await getUserForRead(ctx);
    if (user === null) return [];
    return await ctx.db
      .query("jobs")
      .withIndex("by_user", (q) => q.eq("userId", user._id))
      .order("desc")
      .collect();
  },
});

/** One job, or null when it is missing or not the caller's. */
export const get = query({
  args: { jobId: v.id("jobs") },
  handler: async (ctx, args) => {
    const user = await getUserForRead(ctx);
    if (user === null) return null;
    const job = await ctx.db.get(args.jobId);
    // Null rather than throwing: the client polls this while navigating, and a
    // deleted job should render as "gone", not as an error.
    if (job === null || job.userId !== user._id) return null;
    return job;
  },
});

/** Internal read used by actions, which cannot touch the database directly. */
export const getInternal = internalQuery({
  args: { jobId: v.id("jobs") },
  handler: async (ctx, args) => await ctx.db.get(args.jobId),
});

// ---------------------------------------------------------------------------
// Internal mutations (the transactional half of each action)
// ---------------------------------------------------------------------------

export const insert = internalMutation({
  args: {
    userId: v.id("users"),
    description: v.string(),
    category: taskCategory,
    llmHazardIds: v.union(v.null(), v.array(v.string())),
    llmFollowupFields: v.union(v.null(), v.array(v.string())),
  },
  handler: async (ctx, args) => {
    const draft: JobLike = {
      description: args.description,
      category: args.category,
      followupAnswers: {},
      llmHazardIds: args.llmHazardIds,
      llmFollowupFields: args.llmFollowupFields,
    };

    return await ctx.db.insert("jobs", {
      userId: args.userId,
      description: args.description,
      category: args.category,
      followupAnswers: {},
      llmHazardIds: args.llmHazardIds,
      llmFollowupFields: args.llmFollowupFields,
      nextFollowup: null,
      // Computed at creation with the same function used after every answer, so
      // status is trustworthy immediately rather than only after the first PATCH.
      status: statusFor(draft),
    });
  },
});

export const patch = internalMutation({
  args: {
    jobId: v.id("jobs"),
    followupAnswers: v.optional(v.record(v.string(), followupAnswer)),
    llmHazardIds: v.optional(v.union(v.null(), v.array(v.string()))),
    llmFollowupFields: v.optional(v.union(v.null(), v.array(v.string()))),
    nextFollowup: v.optional(
      v.union(v.null(), v.object({ field: v.string(), question: v.string() })),
    ),
    status: v.optional(
      v.union(
        v.literal("pending_followup"),
        v.literal("ready_to_assess"),
        v.literal("assessed"),
        v.literal("failed"),
      ),
    ),
  },
  handler: async (ctx, args) => {
    const { jobId, ...fields } = args;
    const patchFields = Object.fromEntries(
      Object.entries(fields).filter(([, v]) => v !== undefined),
    );
    await ctx.db.patch(jobId, patchFields);
  },
});

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

/**
 * Create a job from a free-text description.
 *
 * `category` is optional: the conversational intake sends only the description
 * and the category is inferred by the LLM, which validates its own answer
 * against the fixed 9-value set and falls back to "general", so this call site
 * can trust the return value as-is.
 *
 * Hazard tags are resolved HERE, once, and persisted — see jobLogic.hazardIds
 * for the bug that made re-deriving them unacceptable.
 */
export const create = action({
  args: {
    description: v.string(),
    category: v.optional(taskCategory),
  },
  handler: async (ctx, args): Promise<Id<"jobs">> => {
    const user = await ctx.runMutation(internal.jobs.requireUserAction, {});

    const category = args.category ?? (await tagCategory(args.description));
    const tagged = await tagHazardsResult(args.description, category);

    const jobId: Id<"jobs"> = await ctx.runMutation(internal.jobs.insert, {
      userId: user._id,
      description: args.description,
      category,
      // null (not []) when tagging failed, so a job tagged during an outage is
      // retried rather than permanently treated as hazard-free.
      llmHazardIds: tagged === null ? null : tagged.ruleIds,
      llmFollowupFields: tagged === null ? null : tagged.askFields,
    });

    await refreshNextFollowup(ctx, jobId);
    return jobId;
  },
});

/**
 * Merge new follow-up answers into a job.
 *
 * Never silently advances past unanswered safety-critical fields: the status
 * only becomes "ready_to_assess" once every required field has been answered
 * with SOME value, including an explicit `false`.
 */
export const submitFollowup = action({
  args: {
    jobId: v.id("jobs"),
    answers: v.record(v.string(), followupAnswer),
  },
  handler: async (ctx, args): Promise<void> => {
    // Retry tagging first if creation-time tagging failed, so a hazard we only
    // learn about now becomes a question rather than an unanswerable penalty at
    // assessment.
    await ensureHazardIds(ctx, args.jobId);

    const job = await ctx.runQuery(internal.jobs.getInternal, { jobId: args.jobId });
    if (job === null) throw new Error("No job found with that id.");

    const merged = { ...job.followupAnswers, ...args.answers };
    const updated: JobLike = { ...job, followupAnswers: merged };

    await ctx.runMutation(internal.jobs.patch, {
      jobId: args.jobId,
      followupAnswers: merged,
      status: statusFor(updated),
    });

    await refreshNextFollowup(ctx, args.jobId);
  },
});

/**
 * Tag and persist hazard ids for a job that has none yet (null).
 *
 * Covers jobs created during an LLM outage. Re-tagging can only ADD hazards and
 * questions, so it can only widen the required follow-up set — never narrow it.
 * Callers must run this BEFORE the follow-up gate, so any newly discovered
 * question is asked rather than silently penalised.
 */
export async function ensureHazardIds(ctx: ActionCtx, jobId: Id<"jobs">): Promise<void> {
  const job = await ctx.runQuery(internal.jobs.getInternal, { jobId });
  if (job === null) throw new Error("No job found with that id.");
  if (job.llmHazardIds !== null && job.llmHazardIds !== undefined) return;

  const tagged = await tagHazardsResult(job.description, job.category);
  if (tagged === null) return; // still unavailable; stay null and retry next pass

  const updated: JobLike = {
    ...job,
    llmHazardIds: tagged.ruleIds,
    llmFollowupFields: tagged.askFields,
  };

  await ctx.runMutation(internal.jobs.patch, {
    jobId,
    llmHazardIds: tagged.ruleIds,
    llmFollowupFields: tagged.askFields,
    status:
      job.status === "pending_followup" || job.status === "ready_to_assess"
        ? statusFor(updated)
        : undefined,
  });
}

/**
 * Recompute the next unanswered follow-up and its wording.
 *
 * The catalog decides WHICH field; the LLM only supplies wording, and
 * `phraseFollowupQuestion` falls back to a hardcoded phrasing when the LLM is
 * unavailable — the flow never blocks because a model is down.
 */
async function refreshNextFollowup(ctx: ActionCtx, jobId: Id<"jobs">): Promise<void> {
  const job = await ctx.runQuery(internal.jobs.getInternal, { jobId });
  if (job === null) return;

  const field = nextMissingField(job);
  if (field === null) {
    await ctx.runMutation(internal.jobs.patch, { jobId, nextFollowup: null });
    return;
  }

  const question = await phraseFollowupQuestion(field, job.category);
  await ctx.runMutation(internal.jobs.patch, { jobId, nextFollowup: { field, question } });
}

/** Resolve (and create if needed) the calling user, callable from an action. */
export const requireUserAction = internalMutation({
  args: {},
  handler: async (ctx): Promise<Doc<"users">> => {
    const identity = await ctx.auth.getUserIdentity();
    if (identity === null) throw new Error("Not authenticated");

    const existing = await ctx.db
      .query("users")
      .withIndex("by_clerk_id", (q) => q.eq("clerkUserId", identity.subject))
      .unique();
    if (existing !== null) return existing;

    const id = await ctx.db.insert("users", {
      clerkUserId: identity.subject,
      email: identity.email ?? "",
      name: identity.name ?? identity.email?.split("@")[0] ?? "there",
    });
    const created = await ctx.db.get(id);
    if (created === null) throw new Error("Failed to create user");
    return created;
  },
});

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

/**
 * Delete a job and everything hanging off it.
 *
 * The aiLogs rows go too. rules.md §4.6 requires that every assessment attempt
 * IS logged with no sampling — it does not require the log to outlive the user's
 * own task, and those rows embed the task description, so keeping them after the
 * user deletes the conversation would leave exactly the data behind that they
 * asked to be rid of.
 */
export const remove = mutation({
  args: { jobId: v.id("jobs") },
  handler: async (ctx, args) => {
    const user = await requireUser(ctx);
    const job = await getOwnedJob(ctx, args.jobId, user._id);
    await deleteJobChildren(ctx as MutationCtx, job._id);
    await ctx.db.delete(job._id);
  },
});

export { TASK_CATEGORIES };
