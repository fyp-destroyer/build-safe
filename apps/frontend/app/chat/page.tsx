"use client";

// Real Phase 7 conversational task intake, driven by the actual backend
// (jobs/assess/assessments/recommendations — see apps/backend/routers/).
// Replaces the old SCENARIOS script-runner; the JSX/visual structure below
// is kept as close to that version as reasonably possible — see chatData.ts
// history for the removed scripted-demo data.

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { Sidebar } from "@/components/chat/Sidebar";
import { Composer } from "@/components/chat/Composer";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { QuickReplyChips } from "@/components/chat/QuickReplyChips";
import { RiskCard } from "@/components/risk/RiskCard";
import { TypingIndicator } from "@/components/chat/TypingIndicator";
import {
  CATEGORY_ORDER,
  type ChatMessage,
  type HistoryItem,
  type RiskCardData,
  type TaskCategory,
} from "@/lib/chatData";
import type { Profile } from "@/components/settings/SettingsModal";
import { apiFetch, ApiError } from "@/lib/api";
import { getToken, clearToken, getStoredUser } from "@/lib/auth";
import type {
  AssessJobResponse,
  ChatMessagesOut,
  JobOut,
  RecommendationsOut,
  RiskAssessmentOut,
} from "@/lib/types";
import type { RiskLevel } from "@/lib/riskLevels";

// A few example task descriptions to seed the empty-state suggestion chips
// (the old SCENARIOS demo is gone — these just call handleSend with real
// text, same as if the user had typed and hit send).
const EXAMPLE_PROMPTS = [
  "I want to replace a light switch in my bedroom.",
  "I want to repaint my bedroom accent wall.",
  "I need to fix a leaking kitchen faucet.",
];

// Drives the multi-step conversational flow. "idle" -> user hasn't sent a
// task description yet. ask_skill -> the one quick-reply question asked
// before a Job is created (urgency used to be asked here too; it was
// removed because nothing consumed it - see srs.md FR-02). followup ->
// waiting on a
// yes/no answer to `next_followup` from the backend (may loop). assessing
// -> POST /assess + GET /assessments (+ /recommendations) in flight.
// resume_prompt -> user picked an unfinished job from history and is being
// asked whether to continue it. done -> final RiskCard (or error) shown.
type FlowStage =
  | "idle"
  | "ask_skill"
  | "followup"
  | "assessing"
  | "resume_prompt"
  | "done";

let idCounter = 0;
const nextId = () => `m-${++idCounter}`;

// What gets persisted per message. A risk card is stored as a positional
// marker with no text: its contents are re-rendered from the assessment, so
// the transcript can never show a verdict that has drifted from the
// assessment of record (see apps/backend/models/chat_message.py).
type TranscriptEntry =
  | { role: "user" | "assistant"; kind?: "text"; text: string }
  | { role: "assistant"; kind: "risk_card" };

// Key for the job whose conversation is currently on screen, so a refresh
// reopens it instead of dropping the user on an empty chat.
const ACTIVE_JOB_STORAGE_KEY = "buildsafe:active-job-id";

// localStorage access is wrapped because it throws in private-mode Safari
// and when storage is full. Losing the "which chat was open" pointer is a
// minor inconvenience; an exception on every message would not be.
function rememberActiveJob(jobId: string): void {
  try {
    window.localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, jobId);
  } catch {
    /* non-fatal: refresh just won't reopen this chat */
  }
}

function forgetActiveJob(): void {
  try {
    window.localStorage.removeItem(ACTIVE_JOB_STORAGE_KEY);
  } catch {
    /* non-fatal */
  }
}

function readActiveJob(): string | null {
  try {
    return window.localStorage.getItem(ACTIVE_JOB_STORAGE_KEY);
  } catch {
    return null;
  }
}

function truncateTitle(desc: string, max = 50): string {
  const trimmed = desc.trim();
  return trimmed.length > max ? `${trimmed.slice(0, max).trimEnd()}…` : trimmed;
}

function toDisplayCategory(category: string): TaskCategory {
  const upper = category.toUpperCase();
  if (upper === "HVAC") return "HVAC";
  const capitalized = category.charAt(0).toUpperCase() + category.slice(1).toLowerCase();
  return (CATEGORY_ORDER as string[]).includes(capitalized)
    ? (capitalized as TaskCategory)
    : "General";
}

function jobToHistoryItem(job: JobOut, favourite?: boolean): HistoryItem {
  return {
    id: job.id,
    title: truncateTitle(job.description),
    category: toDisplayCategory(job.category),
    createdAt: Date.parse(job.created_at) || Date.now(),
    favourite,
  };
}

// Prettifies raw rule-engine slugs like "gas_hazard" or
// "missing_followup:power_isolated" for display — see assessment.py's
// hazard_tags/triggered_rules docstring.
function prettifyTag(tag: string): string {
  const MISSING_PREFIX = "missing_followup:";
  const isMissing = tag.startsWith(MISSING_PREFIX);
  const body = isMissing ? tag.slice(MISSING_PREFIX.length) : tag;
  const words = body.replace(/_/g, " ").trim();
  const capitalized = words.charAt(0).toUpperCase() + words.slice(1);
  return isMissing ? `Missing/unconfirmed answer: ${capitalized}` : capitalized;
}

// Maps the backend's RiskAssessmentOut (+ optional RecommendationsOut) onto
// the frontend's RiskCardData shape consumed by <RiskCard />. See the task
// spec's "RiskCardData mapping" section for the exact rules this follows.
function buildRiskCardData(
  job: JobOut,
  assessment: RiskAssessmentOut,
  recommendations: RecommendationsOut | null,
): RiskCardData {
  const rawFactors = assessment.hazard_tags.length > 0 ? assessment.hazard_tags : assessment.triggered_rules;
  // The rule engine can report the same rule name more than once (verified
  // against the running backend: a description matching two keyword rules
  // for the same hazard, e.g. "gas" + "gas leak", both add "gas_hazard" to
  // triggered_rules) — de-dupe before mapping to <RiskCard>'s factors list,
  // which keys each <li> by its text and would otherwise get duplicate keys.
  const uniqueFactors = Array.from(new Set(rawFactors));
  // Prefer the backend's plain-language safety notes, which come from the
  // hardcoded rule catalog. Prettified slugs are only a fallback: showing a
  // user "Unsafe followup:load bearing confirmed" (what this did before) is
  // not an explanation, and FR-05 asks for one.
  const notes = assessment.safety_notes ?? [];
  const factors =
    notes.length > 0
      ? Array.from(new Set(notes))
      : uniqueFactors.length > 0
      ? uniqueFactors.map(prettifyTag)
      : assessment.status === "failed"
        ? [
            "The automated risk assessment pipeline failed to complete for this task — it is being treated as the worst plausible case until it can be re-evaluated.",
          ]
        : ["No specific hazard factors were flagged by the automated rule checks for this task."];

  const level = assessment.risk_level as RiskLevel;

  let requiredTools: string[] | undefined;
  let optionalTools: string[] | undefined;
  let toolsWithheld: string | undefined;

  if (level === 5 || assessment.status === "failed") {
    // Never present the placeholder generic-PPE list as real guidance for a
    // Dangerous/Do-Not-Attempt result — withhold tool guidance instead,
    // matching the app's existing level-5 design intent.
    toolsWithheld =
      "Tool and material recommendations are withheld for Dangerous/Do-Not-Attempt tasks. This work requires a licensed professional and must not be attempted as DIY.";
  } else if (recommendations) {
    const required = recommendations.items.filter((i) => i.required).map((i) => i.name);
    const optional = recommendations.items.filter((i) => !i.required).map((i) => i.name);
    requiredTools = required.length > 0 ? required : undefined;
    optionalTools = optional.length > 0 ? optional : undefined;
  }

  const nextStep: RiskCardData["nextStep"] =
    level <= 2
      ? {
          kind: "checklist",
          items: [
            "Review the safety factors listed above before starting",
            recommendations && recommendations.items.length > 0
              ? `Gather the recommended items: ${recommendations.items.map((i) => i.name).join(", ")}`
              : "Gather standard PPE and tools appropriate for this task",
            "Proceed following standard safety practice for this task type",
          ],
        }
      : {
          kind: "consult",
          // NOTE: a specific professional-category recommendation (FR-08,
          // e.g. "Electrician" vs "Structural Engineer") isn't implemented
          // server-side yet — the backend has no such field, so this stays
          // generic rather than inventing specificity the API doesn't give.
          category: "Licensed Professional",
          blurb: `${assessment.explanation} Consult a licensed professional before proceeding with this task.`,
        };

  return {
    level,
    taskTitle: job.description,
    summary: assessment.explanation,
    factors,
    requiredTools,
    optionalTools,
    toolsWithheld,
    cost: assessment.cost ?? "Not yet available",
    time: assessment.time ?? "Not yet available",
    nextStep,
  };
}

export default function ChatPage() {
  const router = useRouter();

  // Gate: nothing renders until we've confirmed a token exists client-side
  // (localStorage isn't readable by Next.js middleware/edge — see the
  // useEffect below).
  const [authChecked, setAuthChecked] = useState(false);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [awaitingReplyOptions, setAwaitingReplyOptions] = useState<string[] | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [activeHistoryId, setActiveHistoryId] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [jobsById, setJobsById] = useState<Record<string, JobOut>>({});
  // Lazy initializer only (never touched by the SSR/hydration render that
  // matters — the tree that reads `profile` is gated behind `authChecked`,
  // which is always false until the client-only effect below flips it, so
  // there's no hydration-mismatch risk from reading localStorage here).
  const [profile, setProfile] = useState<Profile>(() => {
    const stored = getStoredUser();
    return stored ? { name: stored.name, email: stored.email } : { name: "", email: "" };
  });

  const flowStageRef = useRef<FlowStage>("idle");
  const pendingDescriptionRef = useRef<string>("");
  const pendingSkillRef = useRef<string>("");
  const currentJobRef = useRef<JobOut | null>(null);

  // ---- Transcript persistence ----
  // Messages are queued as they're produced and flushed to the backend once
  // a job exists to attach them to. The first two turns (task description,
  // skill question and answer) happen BEFORE POST /jobs, so they have no
  // job_id yet — buffering here rather than writing eagerly is what lets
  // them survive instead of being dropped.
  //
  // Only live conversation is queued. Replaying a stored transcript, or
  // rebuilding an old job's approximation, pushes messages WITHOUT queueing
  // them — otherwise every re-open would append a duplicate copy.
  const transcriptQueueRef = useRef<TranscriptEntry[]>([]);
  const flushingRef = useRef(false);

  const queueTranscript = (entry: TranscriptEntry) => {
    transcriptQueueRef.current.push(entry);
    void flushTranscript();
  };

  const flushTranscript = async () => {
    const jobId = currentJobRef.current?.id;
    if (!jobId || flushingRef.current || transcriptQueueRef.current.length === 0) return;
    flushingRef.current = true;
    const batch = transcriptQueueRef.current;
    transcriptQueueRef.current = [];
    try {
      await apiFetch(`/jobs/${jobId}/messages`, {
        method: "POST",
        body: JSON.stringify({ messages: batch }),
      });
    } catch {
      // Best-effort by design: the transcript is a record of the
      // conversation, never an input to an assessment (see the backend's
      // chat_service docstring). A failed write must not interrupt a safety
      // flow, so re-queue for the next flush and stay silent.
      transcriptQueueRef.current = [...batch, ...transcriptQueueRef.current];
    } finally {
      flushingRef.current = false;
    }
  };

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isTyping]);

  // ---- Auth gate ----
  // Token lives in localStorage (client-only, not readable by middleware/
  // edge — see AGENTS.md task spec §2), so this has to be a client-side
  // effect rather than real route middleware. This is the textbook
  // "synchronize with an external system" effect react.dev describes
  // (https://react.dev/learn/you-might-not-need-an-effect#fetching-data)
  // and has no reactive-derived-state alternative — the
  // react-hooks/set-state-in-effect heuristic can't distinguish that from
  // the anti-patterns it targets, hence the explicit suppression.
  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setAuthChecked(true);
  }, [router]);

  // ---- Load sidebar history once auth passes ----
  const refreshJobs = useCallback(async () => {
    try {
      const jobs = await apiFetch<JobOut[]>("/jobs");
      setJobsById((prev) => {
        const next = { ...prev };
        for (const job of jobs) next[job.id] = job;
        return next;
      });
      setHistory((prev) => {
        const favouritesById = new Map(prev.map((h) => [h.id, h.favourite]));
        return jobs.map((job) => jobToHistoryItem(job, favouritesById.get(job.id)));
      });
    } catch {
      // Sidebar history is a nice-to-have on load; a failed fetch here
      // shouldn't block the rest of the chat UI from working.
    }
  }, []);

  // Same rationale as the auth-gate effect above: a genuine one-time fetch
  // synchronized to an external system (the backend's job list) on mount,
  // not derivable from props/state during render.
  useEffect(() => {
    if (!authChecked) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshJobs();
  }, [authChecked, refreshJobs]);

  const restoredRef = useRef(false);
  // Which job to reopen, captured ONCE at mount. Re-reading localStorage
  // later is wrong: starting a new chat writes the new job's id, so the
  // restore effect would then "restore" the conversation already on screen
  // and inject a resume prompt into the middle of it (observed live).
  const jobToRestoreRef = useRef<string | null>(null);
  useEffect(() => {
    jobToRestoreRef.current = readActiveJob();
  }, []);

  // ---- Small helpers ----

  const pushUserMessage = (text: string, { persist = true }: { persist?: boolean } = {}) => {
    setMessages((prev) => [...prev, { id: nextId(), role: "user", text, createdAt: Date.now() }]);
    if (persist) queueTranscript({ role: "user", text });
  };

  const pushErrorMessage = (err: unknown) => {
    const message =
      err instanceof ApiError
        ? err.message
        : "Couldn't reach the server. Check your connection and try again.";
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role: "assistant", text: message, createdAt: Date.now(), isError: true },
    ]);
    // Errors are part of what the user saw; a transcript that silently omits
    // them would misrepresent the conversation on reopen.
    queueTranscript({ role: "assistant", text: message });
  };

  // `persist: false` for UI chrome that is re-emitted every time a chat is
  // opened (the resume prompt). Persisting those would append another copy
  // to the stored transcript on every open, so re-opening a job three times
  // would show the prompt three times.
  const showBotMessage = (
    text: string,
    quickReplies?: string[],
    delay = 900,
    { persist = true }: { persist?: boolean } = {},
  ): Promise<void> =>
    new Promise((resolve) => {
      setIsTyping(true);
      setAwaitingReplyOptions(null);
      window.setTimeout(() => {
        setIsTyping(false);
        setMessages((prev) => [...prev, { id: nextId(), role: "assistant", text, createdAt: Date.now() }]);
        if (persist) queueTranscript({ role: "assistant", text });
        if (quickReplies) setAwaitingReplyOptions(quickReplies);
        resolve();
      }, delay);
    });

  // ---- Assessment ----

  // Guards the followup_incomplete recovery below against ping-ponging with
  // a backend that keeps reporting a missing field we can't surface.
  const followupRecoveryRef = useRef(0);

  const runAssessment = async (job: JobOut) => {
    flowStageRef.current = "assessing";
    setIsTyping(true);
    setAwaitingReplyOptions(null);
    try {
      await apiFetch<AssessJobResponse>(`/jobs/${job.id}/assess`, { method: "POST" });
      const assessment = await apiFetch<RiskAssessmentOut>(`/assessments/${job.id}`);

      // Never request recommendations for a failed assessment — that 409s
      // (recommendation_service.py) and, more importantly, a failed
      // pipeline must never imply real tool guidance exists.
      const recommendations =
        assessment.status === "completed"
          ? await apiFetch<RecommendationsOut>(`/recommendations/${job.id}`)
          : null;

      const riskCard = buildRiskCardData(job, assessment, recommendations);
      setIsTyping(false);
      setMessages((prev) => [...prev, { id: nextId(), role: "assistant", riskCard, createdAt: Date.now() }]);
      // Marker only — the card is rebuilt from the assessment on reload.
      queueTranscript({ role: "assistant", kind: "risk_card" });
      flowStageRef.current = "done";
      void refreshJobs();
    } catch (err) {
      // The backend can discover a safety-critical follow-up at assessment
      // time that it didn't know about at intake (hazard tagging retried
      // after a Gemini outage). It refuses to assess rather than penalise an
      // unanswered question — so ask the question instead of dead-ending on
      // an error the user can't act on.
      if (err instanceof ApiError && err.code === "followup_incomplete" && followupRecoveryRef.current < 3) {
        followupRecoveryRef.current += 1;
        try {
          const refreshed = await apiFetch<JobOut>(`/jobs/${job.id}/followup`, {
            method: "PATCH",
            body: JSON.stringify({ answers: {} }),
          });
          setJobsById((prev) => ({ ...prev, [refreshed.id]: refreshed }));
          if (refreshed.next_followup) {
            setIsTyping(false);
            await processJobFollowup(refreshed);
            return;
          }
        } catch {
          // Fall through to the generic error below rather than looping.
        }
      }
      setIsTyping(false);
      pushErrorMessage(err);
      flowStageRef.current = "done";
    }
  };

  const processJobFollowup = async (job: JobOut) => {
    currentJobRef.current = job;
    if (job.next_followup) {
      flowStageRef.current = "followup";
      await showBotMessage(job.next_followup.question, ["Yes", "No"]);
    } else if (job.status === "assessed" || job.status === "failed") {
      // Re-entering an already-finished job (e.g. via the resume prompt) —
      // nothing left to drive here.
      flowStageRef.current = "done";
    } else {
      // next_followup is null and status isn't a terminal one yet — ready
      // to assess (covers both "ready_to_assess" and, defensively, any
      // other non-terminal status: next_followup is the more specific
      // signal straight from job_service's own missing-followups check).
      await runAssessment(job);
    }
  };

  const createJobAndProceed = async () => {
    followupRecoveryRef.current = 0;
    setIsTyping(true);
    setAwaitingReplyOptions(null);
    try {
      const job = await apiFetch<JobOut>("/jobs", {
        method: "POST",
        body: JSON.stringify({
          description: pendingDescriptionRef.current,
          skill_level: pendingSkillRef.current,
        }),
      });
      setIsTyping(false);
      setJobsById((prev) => ({ ...prev, [job.id]: job }));
      setHistory((prev) => [jobToHistoryItem(job), ...prev]);
      setActiveHistoryId(job.id);
      // The job now exists, so the messages buffered before it did (task
      // description, skill question, skill answer) finally have somewhere to
      // go. Flush before continuing so they're stored in the order they were
      // said, ahead of anything the follow-up step produces.
      currentJobRef.current = job;
      rememberActiveJob(job.id);
      await flushTranscript();
      await processJobFollowup(job);
    } catch (err) {
      setIsTyping(false);
      pushErrorMessage(err);
      flowStageRef.current = "idle";
    }
  };

  const submitFollowupAndProceed = async (answer: boolean) => {
    const job = currentJobRef.current;
    const field = job?.next_followup?.field;
    if (!job || !field) return;
    setIsTyping(true);
    setAwaitingReplyOptions(null);
    try {
      const updated = await apiFetch<JobOut>(`/jobs/${job.id}/followup`, {
        method: "PATCH",
        body: JSON.stringify({ answers: { [field]: answer } }),
      });
      setIsTyping(false);
      setJobsById((prev) => ({ ...prev, [updated.id]: updated }));

      // Any answer — including "No" (the user honestly confirming the
      // unsafe condition) — resolves this field: job_service.py only
      // blocks assessment for a field that's still *unanswered*, not one
      // whose answer happens to be unsafe. A "No" here proceeds straight to
      // assessment, where ai/rule_engine/rules.py's own falsy-answer check
      // escalates final_risk accordingly (verified end-to-end: an honestly
      // "No" gas-line answer produces a real Dangerous/level-5 result, not
      // a permanent block).
      await processJobFollowup(updated);
    } catch (err) {
      setIsTyping(false);
      pushErrorMessage(err);
      flowStageRef.current = "done";
    }
  };

  /** Replay a stored transcript, or return false if there isn't one.
   *
   * Risk-card rows carry no verdict, so the card is rebuilt here from the
   * assessment — one fetch for the whole conversation regardless of how many
   * card markers it contains. If that fetch fails the marker is skipped
   * rather than rendered as an empty or guessed card: showing no card is
   * honest, showing a blank one is not.
   *
   * Returns false when nothing is stored (jobs created before this feature
   * existed), letting the caller fall back to the old reconstruction.
   */
  const replayStoredTranscript = async (job: JobOut): Promise<boolean> => {
    let stored: ChatMessagesOut;
    try {
      stored = await apiFetch<ChatMessagesOut>(`/jobs/${job.id}/messages`);
    } catch {
      return false;
    }
    if (stored.messages.length === 0) return false;

    let riskCard: RiskCardData | null = null;
    if (stored.messages.some((m) => m.kind === "risk_card")) {
      try {
        const assessment = await apiFetch<RiskAssessmentOut>(`/assessments/${job.id}`);
        const recommendations =
          assessment.status === "completed"
            ? await apiFetch<RecommendationsOut>(`/recommendations/${job.id}`)
            : null;
        riskCard = buildRiskCardData(job, assessment, recommendations);
      } catch {
        riskCard = null;
      }
    }

    const replayed: ChatMessage[] = [];
    for (const message of stored.messages) {
      const createdAt = Date.parse(message.created_at) || Date.now();
      if (message.kind === "risk_card") {
        if (riskCard) {
          replayed.push({ id: nextId(), role: "assistant", riskCard, createdAt });
        }
      } else if (message.text) {
        replayed.push({
          id: nextId(),
          role: message.role,
          text: message.text,
          createdAt,
        });
      }
    }

    setMessages(replayed);
    return true;
  };

  const loadFinishedJob = async (job: JobOut) => {
    setIsTyping(true);
    try {
      const assessment = await apiFetch<RiskAssessmentOut>(`/assessments/${job.id}`);
      const recommendations =
        assessment.status === "completed"
          ? await apiFetch<RecommendationsOut>(`/recommendations/${job.id}`)
          : null;
      const riskCard = buildRiskCardData(job, assessment, recommendations);
      setIsTyping(false);
      setMessages((prev) => [...prev, { id: nextId(), role: "assistant", riskCard, createdAt: Date.now() }]);
    } catch (err) {
      setIsTyping(false);
      pushErrorMessage(err);
    }
  };

  // ---- User-facing handlers ----

  const handleSend = (text: string) => {
    if (isTyping) return;
    if (awaitingReplyOptions) {
      handleQuickReply(text);
      return;
    }
    pushUserMessage(text);
    pendingDescriptionRef.current = text;
    flowStageRef.current = "ask_skill";
    void showBotMessage("What's your experience level with this kind of task?", [
      "Beginner",
      "Some experience",
      "Experienced",
    ]);
  };

  const handleQuickReply = (option: string) => {
    setAwaitingReplyOptions(null);
    const stage = flowStageRef.current;
    // "Continue" answers the resume prompt, which is deliberately not
    // persisted (it's re-emitted on every open). Storing the answer without
    // its question would replay as an orphan "Continue" bubble.
    pushUserMessage(option, { persist: stage !== "resume_prompt" });

    if (stage === "ask_skill") {
      pendingSkillRef.current = option;
      void createJobAndProceed();
    } else if (stage === "followup") {
      void submitFollowupAndProceed(option === "Yes");
    } else if (stage === "resume_prompt") {
      const job = currentJobRef.current;
      if (job) void processJobFollowup(job);
    }
  };

  const handleEditMessage = (id: string, text: string) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, text } : m)));
  };

  const handleNewChat = () => {
    // Flush anything still queued for the chat being left, before its job
    // reference is cleared and the queue would have nowhere to go.
    void flushTranscript();
    setMessages([]);
    setAwaitingReplyOptions(null);
    setActiveHistoryId(null);
    flowStageRef.current = "idle";
    pendingDescriptionRef.current = "";
    pendingSkillRef.current = "";
    currentJobRef.current = null;
    transcriptQueueRef.current = [];
    forgetActiveJob();
  };

  const openJob = async (job: JobOut) => {
    setActiveHistoryId(job.id);
    setAwaitingReplyOptions(null);
    currentJobRef.current = job;
    rememberActiveJob(job.id);
    // Anything still queued belongs to the chat being navigated away from,
    // and its job is already set — flush before switching so it isn't
    // mis-attributed to the job being opened.
    await flushTranscript();

    const replayed = await replayStoredTranscript(job);
    if (!replayed) {
      // Pre-transcript job: fall back to the old approximation — the task
      // description plus, for a finished job, a freshly built risk card.
      setMessages([
        {
          id: nextId(),
          role: "user",
          text: job.description,
          createdAt: Date.parse(job.created_at) || Date.now(),
        },
      ]);
    }

    if (job.status === "assessed" || job.status === "failed") {
      flowStageRef.current = "done";
      if (!replayed) await loadFinishedJob(job);
    } else {
      flowStageRef.current = "resume_prompt";
      await showBotMessage("This assessment wasn't finished — continue?", ["Continue"], 500, {
        persist: false,
      });
    }
  };

  const handleSelectHistory = (id: string) => {
    const job = jobsById[id];
    if (!job) return;
    void openJob(job);
  };

  // Reopen whatever chat was on screen before the refresh. Declared here
  // rather than beside the other effects because it calls `openJob`, which
  // is defined just above. Runs once, and only once the job list has
  // arrived — the stored id has to resolve to a job this user owns, so a
  // stale or foreign id simply never matches and is dropped.
  useEffect(() => {
    if (!authChecked || restoredRef.current) return;
    const jobId = jobToRestoreRef.current;
    if (!jobId) return;
    // The job list can arrive after the user has already started talking.
    // Restoring on top of that would wipe a live conversation, so once the
    // flow has left "idle" the restore is abandoned, not queued.
    if (flowStageRef.current !== "idle") {
      restoredRef.current = true;
      return;
    }
    const job = jobsById[jobId];
    if (!job) return; // job list hasn't arrived yet, or the job is gone
    restoredRef.current = true;
    // Same rationale as the auth-gate and job-list effects above: a one-time
    // fetch synchronized to an external system (the stored transcript) on
    // mount, not state derivable during render.
    void openJob(job);
    // `openJob` is recreated every render and is deliberately not a
    // dependency: restoredRef already limits this to one run, and listing it
    // would re-trigger the restore on every render instead.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authChecked, jobsById]);

  const handleClearHistory = () => {
    setHistory([]);
    setActiveHistoryId(null);
  };

  const handleToggleFavourite = (id: string) => {
    setHistory((prev) => prev.map((h) => (h.id === id ? { ...h, favourite: !h.favourite } : h)));
  };

  const handleExportHistory = () => {
    const blob = new Blob([JSON.stringify(history, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "buildsafe-assessment-history.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDeleteAccount = () => {
    // No DELETE /users/me endpoint exists on the backend yet (out of scope
    // for this pass) — this clears local state/session so the UI reflects
    // "logged out" rather than silently doing nothing.
    clearToken();
    setHistory([]);
    setMessages([]);
    setActiveHistoryId(null);
    router.push("/login");
  };

  if (!authChecked) {
    return <div className="flex h-screen items-center justify-center bg-[var(--color-bg)]" />;
  }

  const isEmpty = messages.length === 0;

  return (
    <div className="flex h-screen bg-[var(--color-bg)] text-[var(--color-text-primary)]">
      <Sidebar
        activeId={activeHistoryId}
        onNewChat={handleNewChat}
        onSelectHistory={handleSelectHistory}
        history={history}
        onToggleFavourite={handleToggleFavourite}
        profile={profile}
        onProfileChange={setProfile}
        onClearHistory={handleClearHistory}
        onExportHistory={handleExportHistory}
        onDeleteAccount={handleDeleteAccount}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        {isEmpty ? (
          <div className="flex flex-1 flex-col items-center justify-center px-4">
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="mb-6 flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-accent)] text-sm font-bold text-white">
                B
              </div>
              <h1 className="text-xl font-semibold">Describe the task. We&apos;ll tell you if it&apos;s safe.</h1>
            </motion.div>
            <div className="w-full max-w-[680px]">
              <Composer onSend={handleSend} autoFocus />
              <div className="mt-3 flex flex-wrap justify-center gap-2 px-4">
                {EXAMPLE_PROMPTS.map((prompt, i) => (
                  <motion.button
                    key={prompt}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 + i * 0.05 }}
                    onClick={() => handleSend(prompt)}
                    className="cursor-pointer rounded-full border border-[var(--color-accent)]/25 px-3.5 py-1.5 text-sm text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)]/10 hover:text-[var(--color-text-primary)]"
                  >
                    {prompt}
                  </motion.button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6 [scrollbar-gutter:stable]">
              <div className="relative mx-auto flex max-w-[680px] flex-col gap-4">
                <div aria-hidden className="pointer-events-none absolute -left-4 bottom-0 top-0 w-px bg-[var(--color-accent)]/25" />
                <AnimatePresence initial={false}>
                  {messages.map((m) => (
                    <div key={m.id} className="flex flex-col gap-2">
                      {m.isError ? (
                        <div className="flex justify-start">
                          <div className="max-w-[80%] rounded-2xl border border-[var(--color-error)]/40 bg-[var(--color-error)]/10 px-3.5 py-2 text-sm text-[var(--color-error)]">
                            {m.text}
                          </div>
                        </div>
                      ) : (
                        m.text && <MessageBubble message={m} onEdit={handleEditMessage} />
                      )}
                      {m.riskCard && <RiskCard data={m.riskCard} />}
                    </div>
                  ))}
                </AnimatePresence>

                {isTyping && (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start">
                    <TypingIndicator />
                  </motion.div>
                )}

                {awaitingReplyOptions && !isTyping && (
                  <div className="flex justify-start">
                    <QuickReplyChips options={awaitingReplyOptions} onSelect={handleQuickReply} />
                  </div>
                )}
              </div>
            </div>
            <Composer onSend={handleSend} disabled={!!awaitingReplyOptions || isTyping} />
          </>
        )}
      </div>
    </div>
  );
}
