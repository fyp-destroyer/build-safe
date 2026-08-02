/**
 * The conversation transcript for a job.
 *
 * Ported from apps/backend/services/chat_service.py + routers/jobs.py.
 *
 * WHAT IS DELIBERATELY NOT STORED HERE
 * ------------------------------------
 * The risk verdict. A `kind: "risk_card"` row carries no risk level, no hazard
 * list and no explanation — only a marker saying "the card belongs at this point
 * in the conversation". The card is re-rendered from the riskAssessments row at
 * read time.
 *
 * That is a safety property, not a storage optimisation: a second copy of a
 * verdict in the chat log could drift from the assessment of record (if an
 * assessment is ever re-run, corrected, or invalidated) and the user would be
 * shown a stale risk level presented as current. There is exactly one place a
 * risk level lives, and the transcript points at it rather than duplicating it.
 */

import { v } from "convex/values";
import { mutation, query } from "./_generated/server";
import { requireUser, getUserForRead } from "./users";
import { getOwnedJob } from "./jobs";

/** A job's transcript, in explicit position order. */
export const list = query({
  args: { jobId: v.id("jobs") },
  handler: async (ctx, args) => {
    const user = await getUserForRead(ctx);
    if (user === null) return [];
    const job = await ctx.db.get(args.jobId);
    if (job === null || job.userId !== user._id) return [];

    const messages = await ctx.db
      .query("chatMessages")
      .withIndex("by_job", (q) => q.eq("jobId", args.jobId))
      .collect();

    // Sort by explicit position, not by creation time: a batch is written in one
    // transaction and _creationTime can tie at that resolution, which would let a
    // transcript render out of order — the one thing storing it must get right.
    return messages.sort((a, b) => a.position - b.position);
  },
});

/**
 * Append a batch of messages.
 *
 * Batched rather than one call per message so the whole exchange lands in a
 * single transaction, which is what makes `position` reliable.
 */
export const appendBatch = mutation({
  args: {
    jobId: v.id("jobs"),
    messages: v.array(
      v.object({
        role: v.union(v.literal("user"), v.literal("assistant")),
        kind: v.union(v.literal("text"), v.literal("risk_card")),
        text: v.optional(v.union(v.null(), v.string())),
      }),
    ),
  },
  handler: async (ctx, args) => {
    const user = await requireUser(ctx);
    const job = await getOwnedJob(ctx, args.jobId, user._id);

    // Continue numbering from whatever is already stored, so a second batch
    // never collides with the first.
    const existing = await ctx.db
      .query("chatMessages")
      .withIndex("by_job", (q) => q.eq("jobId", job._id))
      .collect();
    let position = existing.reduce((max, m) => Math.max(max, m.position), -1) + 1;

    for (const message of args.messages) {
      // Enforce the no-verdict-in-the-transcript rule at the write boundary, not
      // just by convention. A risk_card row that carried text would be a second
      // copy of a verdict, free to drift from the assessment of record.
      if (message.kind === "risk_card" && message.text != null && message.text !== "") {
        throw new Error(
          "A risk_card message must not carry text — the card is rendered from " +
            "the assessment at read time.",
        );
      }

      await ctx.db.insert("chatMessages", {
        userId: user._id,
        jobId: job._id,
        role: message.role,
        kind: message.kind,
        text: message.kind === "risk_card" ? null : (message.text ?? null),
        position: position++,
      });
    }
  },
});
