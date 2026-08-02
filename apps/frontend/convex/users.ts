/**
 * User identity — the bridge between Clerk's account and this app's data.
 *
 * There is exactly one role, `user`. There is no `admin` and no `professional`
 * role, by design (prd.md §4, rules.md §3). Authorization in this app is
 * ownership scoping, not roles: you can reach a row if it is yours, and
 * otherwise it does not exist as far as you are concerned.
 */

import { v } from "convex/values";
import { internalMutation, mutation, query } from "./_generated/server";
import type { Doc, Id } from "./_generated/dataModel";
import type { MutationCtx, QueryCtx } from "./_generated/server";

/**
 * The `users` row for the caller, or null if unauthenticated / not yet created.
 *
 * Read-only: a query cannot write, so this cannot create the row. Callers that
 * need the row to exist use `getOrCreateCurrent` (a mutation) — in practice the
 * client calls that once on mount and every subsequent query finds the row.
 */
export async function getCurrentUser(ctx: QueryCtx): Promise<Doc<"users"> | null> {
  const identity = await ctx.auth.getUserIdentity();
  if (identity === null) return null;

  return await ctx.db
    .query("users")
    .withIndex("by_clerk_id", (q) => q.eq("clerkUserId", identity.subject))
    .unique();
}

/**
 * The caller's user row, or throw.
 *
 * Every user-facing mutation starts here. Throwing rather than returning null is
 * deliberate: a caller that forgets to check a null would otherwise fall through
 * to an unscoped query and leak another user's data.
 *
 * The two failure modes are reported separately on purpose. Collapsing them into
 * one "Not authenticated" was actively misleading: a user who had just signed in
 * with Google — correctly authenticated, Clerk row and all — got told they were
 * not authenticated, simply because their `users` row had not been created yet.
 * That sends anyone debugging it straight at the auth wiring, which is fine.
 */
export async function requireUser(ctx: QueryCtx): Promise<Doc<"users">> {
  const identity = await ctx.auth.getUserIdentity();
  if (identity === null) throw new Error("Not authenticated");

  const user = await getCurrentUser(ctx);
  if (user === null) {
    throw new Error(
      "Signed in, but no user record exists yet. Call users.getOrCreateCurrent first.",
    );
  }
  return user;
}

/**
 * The caller's user row, or null — for READ paths.
 *
 * Queries cannot create the row (they cannot write), and a signed-in user whose
 * row has not been created yet has, by definition, no jobs and no messages. So a
 * read should return "nothing" rather than throw: the alternative is that the
 * whole chat screen errors during the brief window between signing in and the
 * bootstrap mutation landing.
 *
 * Safe precisely because there is nothing to leak — every caller uses it to scope
 * a query it would otherwise run for a real user id.
 */
export async function getUserForRead(ctx: QueryCtx): Promise<Doc<"users"> | null> {
  return await getCurrentUser(ctx);
}

/** The signed-in user, for the sidebar/header. Null when signed out. */
export const current = query({
  args: {},
  handler: async (ctx) => await getCurrentUser(ctx),
});

/**
 * Create the caller's `users` row if it does not exist yet, and return it.
 *
 * This is the JIT half of user sync, and the reason no `user.created` webhook is
 * required: `ctx.auth.getUserIdentity()` already carries the subject, email and
 * name, so the row can be materialised the moment it is first needed. That
 * removes the window a create-webhook would open, in which a signed-in user has
 * no row and every query has to handle "authenticated but unknown".
 *
 * Idempotent — safe to call on every mount.
 */
export const getOrCreateCurrent = mutation({
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
      // `name` is Clerk's assembled full name; fall back to the local part of
      // the email so the sidebar never greets an empty string.
      name: identity.name ?? identity.email?.split("@")[0] ?? "there",
    });

    const created = await ctx.db.get(id);
    if (created === null) throw new Error("Failed to create user");
    return created;
  },
});

/**
 * Upsert from a Clerk `user.created` / `user.updated` webhook.
 *
 * Internal: callable only by other Convex functions (here, the verified webhook
 * handler in http.ts), never by a client.
 */
export const upsertFromClerk = internalMutation({
  args: {
    clerkUserId: v.string(),
    email: v.string(),
    name: v.string(),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("users")
      .withIndex("by_clerk_id", (q) => q.eq("clerkUserId", args.clerkUserId))
      .unique();

    if (existing === null) {
      await ctx.db.insert("users", args);
      return;
    }

    // Only overwrite with non-empty values. A webhook payload missing an email
    // must not blank out a good one we already hold.
    await ctx.db.patch(existing._id, {
      email: args.email || existing.email,
      name: args.name || existing.name,
    });
  },
});

/**
 * Delete everything belonging to a Clerk user, on `user.deleted`.
 *
 * Convex has no cascading deletes, so the cascade is explicit here. The order is
 * children-before-parent so a failure part-way through never leaves a row
 * pointing at a document that no longer exists.
 *
 * `aiLogs` rows go too. rules.md §4.6 requires that every assessment attempt IS
 * logged, with no sampling; it does not require the log to outlive the account
 * that produced it. Those rows embed the task description, so retaining them
 * after the user deleted their account would keep exactly the personal data they
 * asked to be rid of.
 */
export const deleteFromClerk = internalMutation({
  args: { clerkUserId: v.string() },
  handler: async (ctx, args) => {
    const user = await ctx.db
      .query("users")
      .withIndex("by_clerk_id", (q) => q.eq("clerkUserId", args.clerkUserId))
      .unique();

    if (user === null) {
      console.info(`users.deleteFromClerk: no row for ${args.clerkUserId}, nothing to do`);
      return;
    }

    const jobs = await ctx.db
      .query("jobs")
      .withIndex("by_user", (q) => q.eq("userId", user._id))
      .collect();

    for (const job of jobs) {
      await deleteJobChildren(ctx, job._id);
      await ctx.db.delete(job._id);
    }

    await ctx.db.delete(user._id);
    console.info(`users.deleteFromClerk: removed user and ${jobs.length} job(s)`);
  },
});

/**
 * Delete a job's transcript, assessment and AI logs.
 *
 * Shared by account deletion and by `jobs.remove`, so the two can never drift
 * into deleting different subsets.
 */
export async function deleteJobChildren(ctx: MutationCtx, jobId: Id<"jobs">): Promise<void> {
  const messages = await ctx.db
    .query("chatMessages")
    .withIndex("by_job", (q) => q.eq("jobId", jobId))
    .collect();
  for (const m of messages) await ctx.db.delete(m._id);

  const assessments = await ctx.db
    .query("riskAssessments")
    .withIndex("by_job", (q) => q.eq("jobId", jobId))
    .collect();
  for (const a of assessments) await ctx.db.delete(a._id);

  const logs = await ctx.db
    .query("aiLogs")
    .withIndex("by_job", (q) => q.eq("jobId", jobId))
    .collect();
  for (const l of logs) await ctx.db.delete(l._id);
}
