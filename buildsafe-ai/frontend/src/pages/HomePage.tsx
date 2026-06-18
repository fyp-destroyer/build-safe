import {
  ArrowRight,
  HardHat,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { ChatInput } from "../components/ChatInput";
import { ChatMessage } from "../components/ChatMessage";
import { ChatWindow } from "../components/ChatWindow";
import { FullRiskAssessmentModal } from "../components/FullRiskAssessmentModal";
import { QuickTaskButtons } from "../components/QuickTaskButtons";
import { RiskAssessmentCard } from "../components/RiskAssessmentCard";
import { RiskBadge } from "../components/RiskBadge";
import { TypewriterText } from "../components/TypewriterText";
import { TypingIndicator } from "../components/TypingIndicator";
import { assessTask, planFollowups, updateAssessment } from "../services/api";
import type {
  ActiveAssessmentSession,
  ActionPlanResponse,
  AssessmentRequest,
  AssessmentResponse,
  FollowupPlanResponse,
  DetectedAssessmentUpdate,
  LocationType,
  RiskLevel,
  SkillLevel,
  UpdateAssessmentChangeSummary,
  Urgency,
} from "../types/assessment";

declare global {
  interface Window {
    __buildSafeActiveAssessmentSession?: ActiveAssessmentSession | null;
  }
}

type ChatState =
  | "idle"
  | "planning_followups"
  | "asking_followups"
  | "assessing"
  | "updating_assessment"
  | "showing_result"
  | "error";

type ErrorStage = "planning_followups" | "assessing" | "updating_assessment" | null;
type ChatTextTone = "default" | "highlight" | "warning";

type ChatEntry =
  | {
      id: string;
      kind: "text";
      role: "assistant" | "user";
      text: string;
      tone?: ChatTextTone;
      animate?: boolean;
    }
  | {
      id: string;
      kind: "assessment";
      role: "assistant";
      result: AssessmentResponse;
      requestSnapshot: AssessmentRequest;
      planSnapshot: FollowupPlanResponse | null;
      previousResult?: AssessmentResponse | null;
      changeSummary?: UpdateAssessmentChangeSummary | null;
      isUpdate?: boolean;
      animate?: boolean;
    };

type AssessmentMessage = Extract<ChatEntry, { kind: "assessment" }>;

interface OptionButton {
  label: string;
  value: string;
}

const quickTasks = [
  "Replace a light bulb",
  "Install ceiling fan",
  "Fix leaking pipe",
  "Break a wall",
  "Paint my bedroom",
];

const planningStatuses = [
  "Understanding your task...",
  "Checking possible safety hazards...",
  "Identifying the most important follow-up questions...",
  "Assessing whether this needs a professional...",
];

const assessingStatuses = [
  "Evaluating risk level...",
  "Checking safety rules...",
  "Preparing your risk report...",
  "Matching tools, PPE, and professional category...",
];

const updatingStatuses = [
  "Updating assessment...",
  "Checking which risk factors changed...",
  "Recalculating relevant sections...",
];

const riskLegend: RiskLevel[] = [
  "Safe DIY",
  "DIY with supervision",
  "Professional recommended",
  "Professional required",
  "Dangerous / permit-required / do not attempt",
];

export function HomePage(): JSX.Element {
  const [chatState, setChatState] = useState<ChatState>("idle");
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [draft, setDraft] = useState<AssessmentRequest>(createEmptyDraft());
  const [followupPlan, setFollowupPlan] = useState<FollowupPlanResponse | null>(null);
  const [activeAssessmentSession, setActiveAssessmentSession] =
    useState<ActiveAssessmentSession | null>(null);
  const [activeQuestionIndex, setActiveQuestionIndex] = useState(0);
  const [composerValue, setComposerValue] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const [errorStage, setErrorStage] = useState<ErrorStage>(null);
  const [expandedAssessment, setExpandedAssessment] = useState<AssessmentMessage | null>(null);
  const messageIdRef = useRef(0);
  const lastUpdateMessageRef = useRef<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const activeQuestion =
    followupPlan?.follow_up_questions[activeQuestionIndex] ?? null;
  const indicatorMessages = useMemo(() => {
    if (chatState === "planning_followups") {
      return planningStatuses;
    }
    if (chatState === "assessing") {
      return assessingStatuses;
    }
    if (chatState === "updating_assessment") {
      return updatingStatuses;
    }
    return [];
  }, [chatState]);

  useEffect(() => {
    resetConversation();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      block: "end",
      behavior: "smooth",
    });
  }, [messages, chatState, activeQuestionIndex]);

  useEffect(() => {
    if (import.meta.env.DEV) {
      window.__buildSafeActiveAssessmentSession = activeAssessmentSession;
    }
  }, [activeAssessmentSession]);

  function nextMessageId(): string {
    messageIdRef.current += 1;
    return `msg-${messageIdRef.current}`;
  }

  function appendTextMessage(
    role: "assistant" | "user",
    text: string,
    tone: ChatTextTone = "default",
    animate = role === "assistant",
  ): void {
    setMessages((current) => [
      ...current,
      {
        id: nextMessageId(),
        kind: "text",
        role,
        text,
        tone,
        animate,
      },
    ]);
  }

  function resetConversation(): void {
    setMessages([
      {
        id: nextMessageId(),
        kind: "text",
        role: "assistant",
        tone: "highlight",
        animate: true,
        text:
          "BuildSafe AI is a safety-first construction triage assistant. I focus on whether a task looks suitable for DIY, needs supervision, or should be handed to a qualified professional.\n\nTell me the task you want to assess. I'll keep follow-up questions to the minimum needed for a safe decision.",
      },
    ]);
    setChatState("idle");
    setDraft(createEmptyDraft());
    setFollowupPlan(null);
    setActiveQuestionIndex(0);
    setComposerValue("");
    setInputError(null);
    setSubmissionError(null);
    setErrorStage(null);
    setExpandedAssessment(null);
    setActiveAssessmentSession(null);
    lastUpdateMessageRef.current = null;
  }

  function handleSubmit(rawInput?: string): void {
    const input = normalizeInput(rawInput ?? composerValue);
    if (!input) {
      setInputError("Enter a task or answer before sending.");
      return;
    }

    if (chatState === "idle") {
      void handleTaskSubmission(input);
      return;
    }

    if (chatState === "asking_followups" && activeQuestion) {
      void handleFollowupAnswer(activeQuestion, input);
      return;
    }

    if (chatState === "showing_result" && activeAssessmentSession) {
      if (detectLikelyNewTaskIntent(input, activeAssessmentSession.task_intent)) {
        setInputError(null);
        setComposerValue("");
        appendTextMessage("user", input, "default", false);
        appendTextMessage(
          "assistant",
          "This sounds like a new task. Do you want to start a new assessment?",
          "warning",
        );
        return;
      }

      void handleAssessmentUpdate(input, activeAssessmentSession);
    }
  }

  async function handleTaskSubmission(taskDescription: string): Promise<void> {
    if (taskDescription.length < 3) {
      setInputError("Enter a task with at least 3 characters.");
      return;
    }
    if (taskDescription.length > 300) {
      setInputError("Keep the task description under 300 characters.");
      return;
    }

    const nextDraft = {
      ...createEmptyDraft(),
      task_description: taskDescription,
    };

    setInputError(null);
    setSubmissionError(null);
    setErrorStage(null);
    setActiveAssessmentSession(null);
    setComposerValue("");
    setDraft(nextDraft);
    appendTextMessage("user", taskDescription, "default", false);
    setChatState("planning_followups");

    try {
      const plan = await planFollowups({
        task_description: taskDescription,
        known_answers: {},
      });

      setFollowupPlan(plan);
      setActiveQuestionIndex(0);

      if (plan.follow_up_questions.length === 0) {
        await submitAssessment(nextDraft, plan);
        return;
      }

      appendTextMessage(
        "assistant",
        buildFollowupPrompt(plan, plan.follow_up_questions[0]),
        getPlannerTone(plan),
      );
      setChatState("asking_followups");
    } catch (caughtError) {
      const errorMessage =
        caughtError instanceof Error ? caughtError.message : "Follow-up planning failed";
      setSubmissionError(errorMessage);
      setErrorStage("planning_followups");
      setChatState("error");
      appendTextMessage(
        "assistant",
        `I couldn't plan the follow-up questions because the API returned an error: ${errorMessage}`,
        "warning",
      );
    }
  }

  async function handleFollowupAnswer(
    question: string,
    answer: string,
  ): Promise<void> {
    if (answer.length > 180) {
      setInputError("Keep each follow-up answer under 180 characters.");
      return;
    }

    const nextDraft = applyFollowupAnswer(draft, question, answer);

    setInputError(null);
    setSubmissionError(null);
    setErrorStage(null);
    setComposerValue("");
    setDraft(nextDraft);
    appendTextMessage("user", answer, "default", false);

    const nextQuestionIndex = activeQuestionIndex + 1;
    if (followupPlan && nextQuestionIndex < followupPlan.follow_up_questions.length) {
      setActiveQuestionIndex(nextQuestionIndex);
      appendTextMessage(
        "assistant",
        followupPlan.follow_up_questions[nextQuestionIndex],
      );
      return;
    }

    await submitAssessment(nextDraft, followupPlan);
  }

  async function submitAssessment(
    payload: AssessmentRequest,
    planSnapshot: FollowupPlanResponse | null = followupPlan,
  ): Promise<void> {
    setChatState("assessing");
    setSubmissionError(null);
    setErrorStage(null);

    try {
      const result = await assessTask(payload);

      persistAssessmentSession(payload, result);
      setMessages((current) => [
        ...current,
        {
          id: nextMessageId(),
          kind: "assessment",
          role: "assistant",
          result,
          requestSnapshot: payload,
          planSnapshot,
          animate: true,
        },
      ]);
      setChatState("showing_result");
    } catch (caughtError) {
      const errorMessage =
        caughtError instanceof Error ? caughtError.message : "Assessment failed";
      setSubmissionError(errorMessage);
      setErrorStage("assessing");
      setChatState("error");
      appendTextMessage(
        "assistant",
        `I couldn't generate the final assessment because the API returned an error: ${errorMessage}`,
        "warning",
      );
    }
  }

  async function handleAssessmentUpdate(
    updateMessage: string,
    session: ActiveAssessmentSession,
  ): Promise<void> {
    setInputError(null);
    setSubmissionError(null);
    setErrorStage(null);
    setComposerValue("");
    lastUpdateMessageRef.current = updateMessage;
    appendTextMessage("user", updateMessage, "default", false);
    setChatState("updating_assessment");

    try {
      const response = await updateAssessment({
        session_id: session.session_id,
        previous_assessment: session.latest_assessment,
        task_description: session.original_task_description,
        task_intent: session.task_intent,
        task_category: session.task_category,
        previous_answers: session.followup_answers,
        update_message: updateMessage,
        current_user_context: buildCurrentUserContext(session),
      });

      if (
        response.updated_assessment.task_intent !== session.task_intent &&
        response.updated_assessment.task_intent !== "general_diy"
      ) {
        appendTextMessage(
          "assistant",
          "This sounds like a new task. Do you want to start a new assessment?",
          "warning",
        );
        setChatState("showing_result");
        return;
      }

      const nextContext = mergeUpdateIntoFrontendContext(
        session,
        response.change_summary.detected_updates,
      );
      const nextRequestSnapshot = buildRequestFromSession(
        session,
        nextContext.followupAnswers,
        nextContext.userSkillLevel,
        nextContext.availableTools,
      );
      const actionPlanInvalidation = evaluateActionPlanInvalidation(
        session,
        response.change_summary,
        response.updated_assessment,
      );

      setActiveAssessmentSession((current) => {
        if (!current || current.session_id !== session.session_id) {
          return current;
        }
        const hasExistingPlan = Boolean(current.action_plan);
        const actionPlanStatus = hasExistingPlan
          ? actionPlanInvalidation.invalidated
            ? "outdated"
            : "active"
          : "none";

        return {
          ...current,
          task_intent: response.updated_assessment.task_intent,
          task_category: response.updated_assessment.task_category,
          followup_answers: nextContext.followupAnswers,
          user_skill_level: nextContext.userSkillLevel,
          available_tools: nextContext.availableTools,
          latest_assessment: response.updated_assessment,
          assessment_history: [
            ...current.assessment_history,
            response.updated_assessment,
          ],
          change_summary: response.change_summary,
          action_plan_status: actionPlanStatus,
          action_plan_invalidated: hasExistingPlan && actionPlanInvalidation.invalidated,
          action_plan_invalidation_reason:
            hasExistingPlan && actionPlanInvalidation.invalidated
              ? actionPlanInvalidation.reason
              : null,
        };
      });
      setDraft(nextRequestSnapshot);

      setMessages((current) => [
        ...current,
        {
          id: nextMessageId(),
          kind: "text",
          role: "assistant",
          text: "Assessment updated based on your new information.",
          tone: "highlight",
          animate: true,
        },
        {
          id: nextMessageId(),
          kind: "assessment",
          role: "assistant",
          result: response.updated_assessment,
          requestSnapshot: nextRequestSnapshot,
          planSnapshot: followupPlan,
          previousResult: session.latest_assessment,
          changeSummary: response.change_summary,
          isUpdate: true,
          animate: true,
        },
      ]);
      setChatState("showing_result");
    } catch (caughtError) {
      const errorMessage =
        caughtError instanceof Error ? caughtError.message : "Assessment update failed";
      setSubmissionError(errorMessage);
      setErrorStage("updating_assessment");
      setChatState("error");
      appendTextMessage(
        "assistant",
        `I couldn't update the assessment because the API returned an error: ${errorMessage}`,
        "warning",
      );
    }
  }

  function persistAssessmentSession(
    payload: AssessmentRequest,
    result: AssessmentResponse,
  ): void {
    setActiveAssessmentSession((current) => {
      const history = current?.assessment_history ?? [];

      return {
        session_id: current?.session_id ?? createAssessmentSessionId(),
        original_task_description:
          current?.original_task_description ?? payload.task_description,
        task_intent: result.task_intent,
        task_category: result.task_category,
        followup_answers: { ...payload.answers_to_followups },
        user_skill_level: payload.user_skill_level,
        available_tools: [...payload.available_tools],
        location_type: payload.location_type,
        urgency: payload.urgency,
        budget_range: payload.budget_range,
        latest_assessment: result,
        assessment_history: [...history, result],
        change_summary: null,
        action_plan: current?.action_plan ?? null,
        action_plan_status: current?.action_plan ? "outdated" : "none",
        action_plan_invalidated: false,
        action_plan_invalidation_reason: null,
      };
    });
  }

  function handleActionPlanGenerated(plan: ActionPlanResponse): void {
    setActiveAssessmentSession((current) => {
      if (!current) {
        return current;
      }

      return {
        ...current,
        action_plan: plan,
        action_plan_status: "active",
        action_plan_invalidated: false,
        action_plan_invalidation_reason: null,
      };
    });
  }

  async function handleRetry(): Promise<void> {
    if (errorStage === "planning_followups") {
      await handleTaskSubmission(draft.task_description);
      return;
    }
    if (errorStage === "assessing" && draft.task_description) {
      await submitAssessment(draft, followupPlan);
      return;
    }
    if (
      errorStage === "updating_assessment" &&
      activeAssessmentSession &&
      lastUpdateMessageRef.current
    ) {
      await handleAssessmentUpdate(lastUpdateMessageRef.current, activeAssessmentSession);
    }
  }

  const composerConfig = getComposerConfig(chatState, activeQuestion);
  const optionButtons = getOptionsForQuestion(activeQuestion);
  const isInputDisabled =
    chatState === "planning_followups" ||
    chatState === "assessing" ||
    chatState === "updating_assessment" ||
    (chatState === "error" && errorStage === "assessing");

  return (
    <div className="min-h-dvh overflow-x-hidden px-3 py-3 text-stone-950 sm:px-5 sm:py-5 lg:h-dvh lg:overflow-hidden lg:px-8">
      <div className="mx-auto grid min-h-0 w-full max-w-7xl gap-4 lg:h-full lg:grid-cols-[320px_minmax(0,1fr)] lg:gap-6">
        <aside className="grid min-w-0 gap-4 md:grid-cols-3 lg:block lg:min-h-0 lg:space-y-5 lg:overflow-y-auto lg:pr-1">
          <section className="min-w-0 rounded-[22px] border border-white/70 bg-white/80 p-4 shadow-[0_24px_60px_rgba(66,44,16,0.08)] backdrop-blur sm:rounded-[28px] sm:p-6 md:col-span-3 lg:col-span-1">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-stone-950 text-white shadow-lg shadow-amber-950/10 sm:h-14 sm:w-14">
                <HardHat aria-hidden="true" className="h-6 w-6 sm:h-7 sm:w-7" />
              </div>
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-700 sm:text-xs sm:tracking-[0.24em]">
                  Supervisor Demo
                </p>
                <h1 className="display-font mt-1 text-2xl leading-tight text-stone-950 sm:mt-2 sm:text-3xl">
                  BuildSafe AI
                </h1>
                <p className="mt-2 text-sm leading-6 text-stone-600 sm:mt-3">
                  Safety-first construction triage with shorter follow-ups and
                  rule-based final decisions.
                </p>
              </div>
            </div>

            <div className="mt-4 hidden rounded-2xl border border-amber-200/70 bg-gradient-to-br from-amber-100 via-amber-50 to-white p-4 sm:mt-6 sm:rounded-3xl lg:block">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-900">
                Updated flow
              </p>
              <div className="mt-3 space-y-3 text-sm text-stone-700">
                <FlowLine label="1" text="Capture the task in a single first message." />
                <FlowLine label="2" text="Ask at most 1-2 safety-critical follow-ups." />
                <FlowLine label="3" text="Run the rule engine as the final authority." />
                <FlowLine label="4" text="Return a structured risk report without unsafe DIY guidance." />
              </div>
            </div>
          </section>

          <section className="hidden min-w-0 rounded-[22px] border border-white/70 bg-white/80 p-4 shadow-[0_18px_48px_rgba(66,44,16,0.08)] backdrop-blur sm:rounded-[28px] sm:p-6 lg:block">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">
                  Risk legend
                </p>
                <h2 className="display-font mt-2 text-xl text-stone-950 sm:text-2xl">
                  Decision tiers
                </h2>
              </div>
              <ShieldCheck aria-hidden="true" className="h-5 w-5 text-teal-700" />
            </div>

            <div className="mt-4 flex flex-col gap-2 sm:mt-5 sm:gap-3">
              {riskLegend.map((riskLevel) => (
                <RiskBadge key={riskLevel} riskLevel={riskLevel} />
              ))}
            </div>
          </section>

          <section className="hidden min-w-0 rounded-[22px] border border-white/70 bg-white/80 p-4 shadow-[0_18px_48px_rgba(66,44,16,0.08)] backdrop-blur sm:rounded-[28px] sm:p-6 lg:block">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">
                  Controls
                </p>
                <h2 className="display-font mt-2 text-xl text-stone-950 sm:text-2xl">
                  Demo actions
                </h2>
              </div>
              <Sparkles aria-hidden="true" className="h-5 w-5 text-amber-700" />
            </div>

            <div className="mt-5 space-y-3">
              <button
                type="button"
                onClick={resetConversation}
                className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-stone-950 px-4 py-3 text-sm font-semibold text-white transition hover:bg-stone-800"
              >
                <RefreshCw aria-hidden="true" className="h-4 w-4" />
                Start new assessment
              </button>

              {submissionError ? (
                <button
                  type="button"
                  onClick={() => void handleRetry()}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-900 transition hover:border-amber-400 hover:bg-amber-100"
                >
                  <ArrowRight aria-hidden="true" className="h-4 w-4" />
                  Retry last request
                </button>
              ) : null}
            </div>

            <div className="mt-5 rounded-2xl border border-stone-200 bg-stone-50 p-4 text-sm leading-6 text-stone-600 sm:rounded-3xl">
              Endpoints in use:{" "}
              <code className="break-all font-semibold text-stone-800">
                POST /api/llm/plan-followups
              </code>{" "}
              and{" "}
              <code className="break-all font-semibold text-stone-800">
                POST /api/assess-task
              </code>
              , and{" "}
              <code className="break-all font-semibold text-stone-800">
                POST /api/action-plan
              </code>
              , plus{" "}
              <code className="break-all font-semibold text-stone-800">
                POST /api/update-assessment
              </code>
            </div>
          </section>
        </aside>

        <div className="min-h-0 min-w-0 lg:h-full">
          <ChatWindow
            scrollRef={scrollRef}
            footer={
              <ChatInput
                value={composerValue}
                onChange={setComposerValue}
                onSubmit={() => handleSubmit()}
                disabled={isInputDisabled}
                placeholder={composerConfig.placeholder}
                rows={composerConfig.rows}
                options={optionButtons}
                onSelectOption={(value) => handleSubmit(value)}
                error={inputError ?? submissionError}
              />
            }
          >
            <div className="min-w-0 space-y-5">
              {messages.map((message) => {
                if (message.kind === "text") {
                  return (
                    <ChatMessage key={message.id} role={message.role} tone={message.tone}>
                      {message.role === "assistant" ? (
                        <TypewriterText
                          text={message.text}
                          animate={message.animate ?? true}
                        />
                      ) : (
                        message.text
                      )}
                    </ChatMessage>
                  );
                }

                const isLatestAssessment =
                  activeAssessmentSession?.latest_assessment === message.result;
                const planStatusForCard =
                  isLatestAssessment && activeAssessmentSession
                    ? activeAssessmentSession.action_plan_status
                    : activeAssessmentSession?.action_plan_status === "outdated"
                      ? "outdated"
                      : "none";

                return (
                  <ChatMessage key={message.id} role="assistant">
                    <RiskAssessmentCard
                      result={message.result}
                      request={message.requestSnapshot}
                      animate={message.animate}
                      onOpenDetails={() => setExpandedAssessment(message)}
                      actionPlan={
                        isLatestAssessment ? activeAssessmentSession?.action_plan ?? null : null
                      }
                      actionPlanStatus={planStatusForCard}
                      actionPlanInvalidationReason={
                        activeAssessmentSession?.action_plan_invalidation_reason ?? null
                      }
                      canGenerateActionPlan={isLatestAssessment}
                      onActionPlanGenerated={handleActionPlanGenerated}
                    />
                    {message.isUpdate && message.changeSummary ? (
                      <UpdateChangeSummaryCard
                        summary={message.changeSummary}
                        previousResult={message.previousResult ?? null}
                        currentResult={message.result}
                      />
                    ) : null}
                    <div className="mt-4 flex justify-start">
                      <button
                        type="button"
                        onClick={resetConversation}
                        className="inline-flex min-h-11 items-center gap-2 rounded-full border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-stone-800 transition hover:border-stone-400 hover:bg-stone-50"
                      >
                        <RefreshCw aria-hidden="true" className="h-4 w-4" />
                        Start new assessment
                      </button>
                    </div>
                  </ChatMessage>
                );
              })}

              {chatState === "idle" ? (
                <QuickTaskButtons
                  tasks={quickTasks}
                  onSelect={(task) => handleSubmit(task)}
                />
              ) : null}

              {indicatorMessages.length > 0 ? (
                <TypingIndicator messages={indicatorMessages} />
              ) : null}

              <div ref={messagesEndRef} />
            </div>
          </ChatWindow>
        </div>
      </div>

      {expandedAssessment ? (
        <FullRiskAssessmentModal
          result={expandedAssessment.result}
          request={expandedAssessment.requestSnapshot}
          plan={expandedAssessment.planSnapshot}
          onClose={() => setExpandedAssessment(null)}
        />
      ) : null}
    </div>
  );
}

function FlowLine({ label, text }: { label: string; text: string }): JSX.Element {
  return (
    <div className="flex min-w-0 items-start gap-3">
      <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-stone-950 text-xs font-bold text-white">
        {label}
      </span>
      <p className="min-w-0 break-words">{text}</p>
    </div>
  );
}

function UpdateChangeSummaryCard({
  summary,
  previousResult,
  currentResult,
}: {
  summary: UpdateAssessmentChangeSummary;
  previousResult: AssessmentResponse | null;
  currentResult: AssessmentResponse;
}): JSX.Element {
  const changedItems = buildChangedItems(summary, previousResult, currentResult);
  const unchangedItems = buildUnchangedItems(summary, currentResult);
  const riskLevelChange = summary.risk_level_change;

  return (
    <section className="mt-4 min-w-0 rounded-[22px] border border-amber-200 bg-amber-50/70 p-4 text-stone-900 sm:rounded-[24px]">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-800">
            Assessment update
          </p>
          <h4 className="mt-2 text-lg font-bold text-stone-950">What changed?</h4>
        </div>

        {riskLevelChange ? (
          <div
            className={`rounded-2xl border px-4 py-3 text-sm font-semibold ${
              riskLevelChange.changed
                ? "border-red-200 bg-red-50 text-red-950"
                : "border-emerald-200 bg-emerald-50 text-emerald-950"
            }`}
          >
            {riskLevelChange.changed ? (
              <>
                <span className="block text-xs uppercase tracking-[0.16em]">
                  Risk Level Changed
                </span>
                <span className="mt-1 block">
                  {riskLevelChange.old_level} -&gt; {riskLevelChange.new_level}
                </span>
              </>
            ) : (
              <span>
                Risk level remains {riskLevelChange.new_level}, but some
                recommendations were updated.
              </span>
            )}
          </div>
        ) : null}
      </div>

      <div className="mt-4 grid min-w-0 gap-4 xl:grid-cols-2">
        <SummaryList
          title="What changed"
          items={changedItems}
          emptyLabel="No specific changed sections were returned."
        />
        <SummaryList
          title="What stayed the same"
          items={unchangedItems}
          emptyLabel="No unchanged sections were returned."
        />
      </div>
    </section>
  );
}

function SummaryList({
  title,
  items,
  emptyLabel,
}: {
  title: string;
  items: string[];
  emptyLabel: string;
}): JSX.Element {
  return (
    <div className="min-w-0 rounded-[20px] border border-stone-200 bg-white p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
        {title}
      </p>
      {items.length > 0 ? (
        <ul className="mt-3 space-y-2">
          {items.map((item) => (
            <li key={`${title}-${item}`} className="break-words text-sm leading-6 text-stone-700">
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-stone-500">{emptyLabel}</p>
      )}
    </div>
  );
}

function createEmptyDraft(): AssessmentRequest {
  return {
    task_description: "",
    user_skill_level: "beginner",
    available_tools: [],
    location_type: "house",
    urgency: "low",
    budget_range: "not specified",
    answers_to_followups: {},
  };
}

function getComposerConfig(
  chatState: ChatState,
  activeQuestion: string | null,
): { placeholder: string; rows: number } {
  if (chatState === "idle") {
    return {
      placeholder:
        "Example: I want to break a wall between my kitchen and living room.",
      rows: 3,
    };
  }

  if (chatState === "asking_followups" && activeQuestion) {
    return {
      placeholder: `Answer: ${activeQuestion}`,
      rows: 2,
    };
  }

  if (chatState === "planning_followups") {
    return {
      placeholder: "Planning the safest follow-up questions...",
      rows: 1,
    };
  }

  if (chatState === "assessing") {
    return {
      placeholder: "Generating your assessment...",
      rows: 1,
    };
  }

  if (chatState === "updating_assessment") {
    return {
      placeholder: "Updating the current assessment...",
      rows: 1,
    };
  }

  if (chatState === "showing_result") {
    return {
      placeholder:
        "Update details: Actually, it weighs 2 kg. The wall is concrete. There may be wiring behind the wall.",
      rows: 2,
    };
  }

  return {
    placeholder: "Start a new assessment to evaluate another task.",
    rows: 1,
  };
}

function getPlannerTone(plan: FollowupPlanResponse): ChatTextTone {
  if (
    plan.suggested_risk_level === "Professional required" ||
    plan.suggested_risk_level === "Dangerous / permit-required / do not attempt"
  ) {
    return "warning";
  }
  return "highlight";
}

function buildPlannerLead(plan: FollowupPlanResponse): string {
  const questionCount = plan.follow_up_questions.length;
  const countText =
    questionCount === 0
      ? "I already have enough context to assess it."
      : questionCount === 1
        ? "I just need 1 quick safety check before I assess it."
        : "I just need 2 quick safety checks before I assess it.";

  return `${plan.short_reason} ${countText}`;
}

function buildFollowupPrompt(
  plan: FollowupPlanResponse,
  question: string,
): string {
  return `${buildPlannerLead(plan)}\n\n${question}`;
}

function applyFollowupAnswer(
  draft: AssessmentRequest,
  question: string,
  answer: string,
): AssessmentRequest {
  const normalizedAnswer = normalizeInput(answer);
  const nextDraft: AssessmentRequest = {
    ...draft,
    answers_to_followups: {
      ...draft.answers_to_followups,
      [question]: normalizedAnswer,
    },
  };

  const loweredQuestion = question.toLowerCase();
  const loweredAnswer = normalizedAnswer.toLowerCase();
  if (
    (loweredQuestion.includes("skill level") || loweredQuestion.includes("experience level")) &&
    isSkillLevel(loweredAnswer)
  ) {
    nextDraft.user_skill_level = loweredAnswer;
  }

  return nextDraft;
}

function getOptionsForQuestion(question: string | null): OptionButton[] {
  if (!question) {
    return [];
  }

  const normalizedQuestion = question.toLowerCase();
  if (normalizedQuestion.includes("skill level") || normalizedQuestion.includes("experience level")) {
    return [
      { label: "Beginner", value: "beginner" },
      { label: "Intermediate", value: "intermediate" },
      { label: "Expert", value: "expert" },
    ];
  }

  if (normalizedQuestion.includes("minor visible joint leak")) {
    return [
      { label: "Minor visible joint", value: "minor visible joint leak" },
      { label: "Hidden/main line", value: "hidden or main line leak" },
      { label: "Not sure", value: "not sure" },
    ];
  }

  if (normalizedQuestion.includes("standard bulb") || normalizedQuestion.includes("wiring or the light fitting")) {
    return [
      { label: "Standard bulb", value: "standard bulb only" },
      { label: "Wiring/fitting", value: "wiring or fitting" },
      { label: "Not sure", value: "not sure" },
    ];
  }

  if (normalizedQuestion.includes("yes") || normalizedQuestion.includes("do you") || normalizedQuestion.includes("is there") || normalizedQuestion.includes("could there")) {
    return [
      { label: "Yes", value: "yes" },
      { label: "No", value: "no" },
      { label: "Not sure", value: "not sure" },
    ];
  }

  return [];
}

function buildCurrentUserContext(
  session: ActiveAssessmentSession,
): Record<string, unknown> {
  return {
    user_skill_level: session.user_skill_level,
    available_tools: session.available_tools,
    location_type: session.location_type,
    urgency: session.urgency,
    budget_range: session.budget_range,
  };
}

function buildRequestFromSession(
  session: ActiveAssessmentSession,
  followupAnswers = session.followup_answers,
  userSkillLevel = session.user_skill_level,
  availableTools = session.available_tools,
): AssessmentRequest {
  return {
    task_description: session.original_task_description,
    user_skill_level: userSkillLevel,
    available_tools: availableTools,
    location_type: session.location_type,
    urgency: session.urgency,
    budget_range: session.budget_range,
    answers_to_followups: followupAnswers,
  };
}

function mergeUpdateIntoFrontendContext(
  session: ActiveAssessmentSession,
  updates: DetectedAssessmentUpdate[],
): {
  followupAnswers: Record<string, string>;
  userSkillLevel: SkillLevel;
  availableTools: string[];
} {
  const followupAnswers = { ...session.followup_answers };
  let userSkillLevel = session.user_skill_level;
  let availableTools = [...session.available_tools];

  updates.forEach((update) => {
    const value = stringifyUpdateValue(update.new_value);
    const label = formatUpdateFieldLabel(update.field);
    followupAnswers[`Updated ${label}`] = value;

    if (update.field === "user_skill_level" && isSkillLevel(value)) {
      userSkillLevel = value;
    }

    if (update.field === "available_tools") {
      availableTools = dedupeStrings([
        ...availableTools,
        ...toStringList(update.new_value),
      ]);
    }

    if (update.field === "unavailable_tools") {
      const unavailable = new Set(
        toStringList(update.new_value).map((item) => item.toLowerCase()),
      );
      availableTools = availableTools.filter(
        (tool) => !unavailable.has(tool.toLowerCase()),
      );
    }
  });

  return {
    followupAnswers,
    userSkillLevel,
    availableTools,
  };
}

function evaluateActionPlanInvalidation(
  session: ActiveAssessmentSession,
  summary: UpdateAssessmentChangeSummary,
  updatedAssessment: AssessmentResponse,
): { invalidated: boolean; reason: string | null } {
  if (!session.action_plan) {
    return { invalidated: false, reason: null };
  }

  const reasons: string[] = [];
  const riskLevelChange = summary.risk_level_change;
  if (riskLevelChange?.changed) {
    reasons.push(
      `Risk level changed from ${riskLevelChange.old_level} to ${riskLevelChange.new_level}.`,
    );
  }

  const riskScoreChange = summary.risk_score_change;
  if (
    typeof riskScoreChange?.old_score === "number" &&
    typeof riskScoreChange.new_score === "number" &&
    riskScoreChange.new_score - riskScoreChange.old_score >= 10
  ) {
    reasons.push("Risk score increased by 10 or more points.");
  }

  const changedSections = new Set(summary.changed_sections);
  if (changedSections.has("safety_warnings")) {
    reasons.push("Safety warnings changed.");
  }
  if (changedSections.has("professional_recommendation")) {
    reasons.push("Professional recommendation changed.");
  }
  if (changedSections.has("task_intent")) {
    reasons.push("Task intent changed.");
  }

  const highImpactUpdateFields = new Set([
    "attachment_method",
    "wall_material",
    "hidden_utilities",
    "electrical_damage",
    "unavailable_tools",
  ]);
  if (summary.detected_updates.some((update) => highImpactUpdateFields.has(update.field))) {
    reasons.push("Required method, material, or safety constraints changed.");
  }

  if (!planTypeMatchesRiskLevel(session.action_plan.plan_type, updatedAssessment.risk_level)) {
    reasons.push("Existing plan type no longer matches the updated risk level.");
  }

  const uniqueReasons = dedupeStrings(reasons);
  return {
    invalidated: uniqueReasons.length > 0,
    reason: uniqueReasons.length > 0 ? uniqueReasons.join(" ") : null,
  };
}

function planTypeMatchesRiskLevel(planType: string, riskLevel: RiskLevel): boolean {
  if (riskLevel === "Safe DIY") {
    return planType === "safe_diy_plan";
  }
  if (riskLevel === "DIY with supervision") {
    return planType === "supervised_plan";
  }
  if (riskLevel === "Professional recommended") {
    return planType === "preparation_checklist";
  }
  return planType === "professional_only_checklist";
}

function buildChangedItems(
  summary: UpdateAssessmentChangeSummary,
  previousResult: AssessmentResponse | null,
  currentResult: AssessmentResponse,
): string[] {
  const items: string[] = [];

  summary.detected_updates.forEach((update) => {
    const label = formatUpdateFieldLabel(update.field);
    const newValue = stringifyUpdateValue(update.new_value);
    const oldValue = stringifyUpdateValue(update.old_value_if_known);
    items.push(
      oldValue
        ? `${label} updated: ${oldValue} -> ${newValue}`
        : `${label} updated: ${newValue}`,
    );
  });

  if (summary.risk_score_change) {
    const direction = getScoreDirection(summary.risk_score_change);
    items.push(
      `Risk score ${direction}: ${summary.risk_score_change.old_score ?? "unknown"} -> ${summary.risk_score_change.new_score ?? "unknown"}`,
    );
  }

  const addedTools = diffAdded(previousResult?.required_tools, currentResult.required_tools);
  const addedMaterials = diffAdded(
    previousResult?.required_materials,
    currentResult.required_materials,
  );
  const addedWarnings = diffAdded(
    previousResult?.safety_warnings,
    currentResult.safety_warnings,
  );

  if (addedTools.length > 0) {
    items.push(`Added tool recommendation: ${addedTools.slice(0, 2).join(", ")}`);
  }
  if (addedMaterials.length > 0) {
    items.push(
      `Added material recommendation: ${addedMaterials.slice(0, 2).join(", ")}`,
    );
  }
  if (addedWarnings.length > 0) {
    items.push(`Added safety warning: ${addedWarnings[0]}`);
  }

  return dedupeStrings(items);
}

function buildUnchangedItems(
  summary: UpdateAssessmentChangeSummary,
  currentResult: AssessmentResponse,
): string[] {
  const sections = new Set(summary.unchanged_sections);
  const items: string[] = [];

  if (sections.has("task_intent")) {
    items.push(`Task intent: ${currentResult.task_intent}`);
  }
  if (sections.has("task_category")) {
    items.push(`Task category: ${currentResult.task_category}`);
  }
  if (sections.has("basic_tools")) {
    items.push(`Basic tools: ${formatListPreview(currentResult.required_tools)}`);
  }
  if (sections.has("materials")) {
    items.push(`Materials: ${formatListPreview(currentResult.required_materials)}`);
  }
  if (sections.has("ppe")) {
    items.push(`PPE: ${formatListPreview(currentResult.required_ppe)}`);
  }
  if (sections.has("professional_recommendation")) {
    items.push(
      `Professional: ${currentResult.recommended_professional_category || "Not required"}`,
    );
  }
  if (sections.has("estimated_time")) {
    items.push(`Estimated time: ${currentResult.estimated_time}`);
  }

  return items;
}

function detectLikelyNewTaskIntent(
  input: string,
  currentTaskIntent: string,
): string | null {
  const text = input.toLowerCase();
  const taskSwitchCue =
    text.includes("actually") ||
    text.includes("instead") ||
    text.includes("rather than") ||
    text.includes("i want to");

  if (!taskSwitchCue) {
    return null;
  }

  const detectedIntent = detectSimpleTaskIntent(text);
  if (detectedIntent && detectedIntent !== currentTaskIntent) {
    return detectedIntent;
  }

  return null;
}

function detectSimpleTaskIntent(text: string): string | null {
  if (
    text.includes("paint the room") ||
    text.includes("paint my room") ||
    text.includes("paint my bedroom") ||
    text.includes("repaint the room") ||
    text.includes("paint the wall") ||
    text.includes("paint the walls")
  ) {
    return "wall_painting";
  }

  if (
    text.includes("break a wall") ||
    text.includes("remove wall") ||
    text.includes("knock down wall") ||
    text.includes("demolition")
  ) {
    return "wall_demolition";
  }

  if (text.includes("ceiling fan")) {
    return "ceiling_fan_installation";
  }

  if (text.includes("replace a light bulb") || text.includes("change light bulb")) {
    return "light_bulb_replacement";
  }

  return null;
}

function formatUpdateFieldLabel(field: string): string {
  const labels: Record<string, string> = {
    painting_weight: "Weight",
    item_weight: "Weight",
    wall_material: "Wall material",
    attachment_method: "Attachment method",
    hidden_utilities: "Hidden utilities",
    available_tools: "Available tools",
    unavailable_tools: "Missing tools",
    user_skill_level: "Skill level",
    electrical_damage: "Electrical damage",
  };

  return labels[field] ?? field.replace(/_/g, " ");
}

function stringifyUpdateValue(value: unknown): string {
  if (value === null || typeof value === "undefined") {
    return "";
  }
  if (Array.isArray(value)) {
    return value.map(stringifyUpdateValue).filter(Boolean).join(", ");
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function toStringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean);
  }
  const normalized = stringifyUpdateValue(value).trim();
  return normalized ? [normalized] : [];
}

function diffAdded(
  previousItems: string[] | null | undefined,
  currentItems: string[],
): string[] {
  const previous = new Set((previousItems ?? []).map((item) => item.toLowerCase()));
  return currentItems.filter((item) => !previous.has(item.toLowerCase()));
}

function formatListPreview(items: string[]): string {
  if (items.length === 0) {
    return "Not listed";
  }
  if (items.length <= 3) {
    return items.join(", ");
  }
  return `${items.slice(0, 3).join(", ")} +${items.length - 3} more`;
}

function getScoreDirection(
  change: NonNullable<UpdateAssessmentChangeSummary["risk_score_change"]>,
): string {
  if (change.old_score === null || change.new_score === null) {
    return "changed";
  }
  if (change.new_score > change.old_score) {
    return "increased";
  }
  if (change.new_score < change.old_score) {
    return "decreased";
  }
  return "remains";
}

function dedupeStrings(values: string[]): string[] {
  return listFromUnique(values.map((value) => value.trim()).filter(Boolean));
}

function listFromUnique(values: string[]): string[] {
  return Array.from(new Set(values));
}

function isSkillLevel(value: string): value is SkillLevel {
  return value === "beginner" || value === "intermediate" || value === "expert";
}

function normalizeInput(input: string): string {
  return input.replace(/\s+/g, " ").trim();
}

function createAssessmentSessionId(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }

  return `assessment-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}
