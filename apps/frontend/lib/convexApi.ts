/**
 * Convex calls, adapted to the wire shapes the chat flow already speaks.
 *
 * WHY AN ADAPTER RATHER THAN A REWRITE
 * ------------------------------------
 * app/chat/page.tsx is a 936-line imperative state machine: `runStep` and
 * `handleSend` await calls mid-flow, and the stage is tracked in a ref precisely
 * because those handlers read it synchronously. Converting that to `useQuery`
 * subscriptions would have meant restructuring the whole flow at the same time
 * as changing its backend — two hard changes at once, in the file most likely to
 * break, with the 4 demo scenarios as the only safety net.
 *
 * So the flow keeps its promise-based shape and this module changes only where
 * the data comes from. Convex documents use `_id`/`_creationTime` and camelCase;
 * the components speak `id`/`created_at` and snake_case. Translating in one
 * place keeps every component under components/ untouched, which is what makes
 * "the design does not change" verifiable rather than hopeful.
 *
 * Where the reactive model genuinely pays for itself — the sidebar list — the
 * page can move to `useQuery` incrementally, since both styles read the same
 * functions.
 */

import type { ConvexReactClient } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Id } from "@/convex/_generated/dataModel";
import type {
  ChatMessagesOut,
  JobOut,
  RecommendationsOut,
  RiskAssessmentOut,
} from "./types";

type Convex = ConvexReactClient;

/** A Convex job document, as returned by the generated API. */
interface JobDoc {
  _id: Id<"jobs">;
  _creationTime: number;
  userId: Id<"users">;
  description: string;
  category: string;
  followupAnswers: Record<string, boolean>;
  llmHazardIds?: string[] | null;
  llmFollowupFields?: string[] | null;
  nextFollowup?: { field: string; question: string } | null;
  status: string;
}

/** Convex document -> the JobOut shape the chat flow and sidebar already use. */
function toJobOut(job: JobDoc): JobOut {
  return {
    id: job._id,
    user_id: job.userId,
    description: job.description,
    category: job.category,
    // Retired from the product (2026-08-02 / 2026-07-31) and no longer stored.
    // Kept on the wire type so the components' props are unchanged.
    skill_level: "",
    urgency: null,
    followup_answers: job.followupAnswers,
    status: job.status as JobOut["status"],
    created_at: new Date(job._creationTime).toISOString(),
    next_followup: job.nextFollowup ?? null,
  };
}

export async function listJobs(convex: Convex): Promise<JobOut[]> {
  const jobs = await convex.query(api.jobs.list, {});
  return (jobs as JobDoc[]).map(toJobOut);
}

async function getJob(convex: Convex, jobId: string): Promise<JobOut> {
  const job = await convex.query(api.jobs.get, { jobId: jobId as Id<"jobs"> });
  if (job === null) throw new Error("No job found with that id.");
  return toJobOut(job as JobDoc);
}

/**
 * Create a job from a free-text description.
 *
 * The action tags category and hazards via the LLM before committing, so the
 * job that comes back already has its follow-up state resolved — the same
 * contract the old POST /jobs had.
 */
export async function createJob(convex: Convex, description: string): Promise<JobOut> {
  const jobId = await convex.action(api.jobs.create, { description });
  return await getJob(convex, jobId as string);
}

export async function submitFollowup(
  convex: Convex,
  jobId: string,
  answers: Record<string, boolean>,
): Promise<JobOut> {
  await convex.action(api.jobs.submitFollowup, {
    jobId: jobId as Id<"jobs">,
    answers,
  });
  return await getJob(convex, jobId);
}

export async function assessJob(
  convex: Convex,
  jobId: string,
): Promise<{ status: string; riskLevel: number | null }> {
  return await convex.action(api.assessments.assess, { jobId: jobId as Id<"jobs"> });
}

export async function getAssessment(
  convex: Convex,
  jobId: string,
): Promise<RiskAssessmentOut> {
  const a = await convex.query(api.assessments.get, { jobId: jobId as Id<"jobs"> });
  if (a === null) throw new Error("No assessment found for that job.");

  return {
    id: a._id,
    job_id: a.jobId,
    risk_level: a.riskLevel,
    confidence: a.confidence,
    explanation: a.explanation,
    hazard_tags: a.hazardTags,
    triggered_rules: a.triggeredRules,
    // Derived server-side from the hardcoded catalog, never stored.
    safety_notes: a.safetyNotes,
    cost: a.cost ?? null,
    time: a.time ?? null,
    difficulty: a.difficulty ?? null,
    status: a.status,
    created_at: new Date(a._creationTime).toISOString(),
  };
}

export async function getRecommendations(
  convex: Convex,
  jobId: string,
): Promise<RecommendationsOut> {
  const r = await convex.query(api.recommendations.get, { jobId: jobId as Id<"jobs"> });
  if (r === null) throw new Error("Recommendations require a completed risk assessment.");

  return {
    job_id: r.jobId,
    risk_level: r.riskLevel,
    items: r.items,
    is_placeholder: r.isPlaceholder,
  };
}

export async function getMessages(convex: Convex, jobId: string): Promise<ChatMessagesOut> {
  const messages = await convex.query(api.chat.list, { jobId: jobId as Id<"jobs"> });
  return {
    messages: messages.map((m) => ({
      id: m._id,
      job_id: m.jobId,
      role: m.role,
      kind: m.kind,
      text: m.text ?? null,
      position: m.position,
      created_at: new Date(m._creationTime).toISOString(),
    })),
  };
}

export async function appendMessages(
  convex: Convex,
  jobId: string,
  messages: {
    role: "user" | "assistant";
    /** Defaults to "text" — the chat flow omits it for ordinary messages. */
    kind?: "text" | "risk_card";
    text?: string | null;
  }[],
): Promise<void> {
  await convex.mutation(api.chat.appendBatch, {
    jobId: jobId as Id<"jobs">,
    messages: messages.map((m) => ({
      role: m.role,
      kind: m.kind ?? "text",
      // A risk_card row must carry no text — the card is rendered from the
      // assessment at read time. Enforced server-side too; normalised here so a
      // caller cannot trip that check by accident.
      text: m.kind === "risk_card" ? null : (m.text ?? null),
    })),
  });
}

export async function deleteJob(convex: Convex, jobId: string): Promise<void> {
  await convex.mutation(api.jobs.remove, { jobId: jobId as Id<"jobs"> });
}
