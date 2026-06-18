import {
  ArrowRight,
  ClipboardCheck,
  Clock3,
  HardHat,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useState } from "react";

import { generateActionPlan } from "../services/api";
import type {
  ActionPlanRequest,
  ActionPlanResponse,
  ActionPlanStatus,
  AssessmentRequest,
  AssessmentResponse,
  RiskLevel,
} from "../types/assessment";
import { ActionPlanModal } from "./ActionPlanModal";
import { RiskBadge } from "./RiskBadge";
import { TypewriterText } from "./TypewriterText";
import {
  formatTaskIntent,
  getCompactSummary,
  getDisplayText,
  getProfessionalLabel,
} from "./riskAssessmentUtils";

interface RiskAssessmentCardProps {
  result: AssessmentResponse;
  request: AssessmentRequest;
  animate?: boolean;
  onOpenDetails: () => void;
  actionPlan?: ActionPlanResponse | null;
  actionPlanStatus?: ActionPlanStatus;
  actionPlanInvalidationReason?: string | null;
  canGenerateActionPlan?: boolean;
  onActionPlanGenerated?: (plan: ActionPlanResponse) => void;
}

const actionPlanStatuses = [
  "Preparing a safe plan...",
  "Checking risk restrictions...",
  "Building your checklist...",
];

export function RiskAssessmentCard({
  result,
  request,
  animate = false,
  onOpenDetails,
  actionPlan: storedActionPlan = null,
  actionPlanStatus = "none",
  actionPlanInvalidationReason = null,
  canGenerateActionPlan = true,
  onActionPlanGenerated,
}: RiskAssessmentCardProps): JSX.Element {
  const [localActionPlan, setLocalActionPlan] = useState<ActionPlanResponse | null>(null);
  const [isActionPlanOpen, setIsActionPlanOpen] = useState(false);
  const [isGeneratingPlan, setIsGeneratingPlan] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);
  const [statusIndex, setStatusIndex] = useState(0);

  const summary = getCompactSummary(result);
  const professionalLabel = getProfessionalLabel(result);
  const actionButton = getActionPlanButtonConfig(result.risk_level);
  const effectiveActionPlan = storedActionPlan ?? localActionPlan;
  const isPlanOutdated = actionPlanStatus === "outdated" && Boolean(effectiveActionPlan);
  const isPlanActive = actionPlanStatus === "active" && Boolean(effectiveActionPlan);
  const actionButtonLabel = isPlanOutdated
    ? "Regenerate Plan"
    : isPlanActive
      ? "View Current Plan"
      : actionButton.label;

  useEffect(() => {
    if (!isGeneratingPlan) {
      setStatusIndex(0);
      return;
    }

    const intervalId = window.setInterval(() => {
      setStatusIndex((current) => (current + 1) % actionPlanStatuses.length);
    }, 1100);

    return () => window.clearInterval(intervalId);
  }, [isGeneratingPlan]);

  async function handleActionPlanClick(): Promise<void> {
    if (!canGenerateActionPlan) {
      setPlanError("Use the latest assessment card to generate a current plan.");
      return;
    }

    if (effectiveActionPlan && !isPlanOutdated) {
      setIsActionPlanOpen(true);
      return;
    }

    setIsGeneratingPlan(true);
    setPlanError(null);

    try {
      const plan = await generateActionPlan(buildActionPlanRequest(result, request));
      setLocalActionPlan(plan);
      onActionPlanGenerated?.(plan);
      setIsActionPlanOpen(true);
    } catch (caughtError) {
      setPlanError(
        caughtError instanceof Error ? caughtError.message : "Unable to generate action plan",
      );
    } finally {
      setIsGeneratingPlan(false);
    }
  }

  return (
    <article className="w-full min-w-0 overflow-hidden rounded-[22px] border border-stone-200 bg-[linear-gradient(180deg,#fffdf8_0%,#ffffff_44%,#f4efe7_100%)] text-left text-stone-900 shadow-sm sm:rounded-[28px]">
      <div className="hazard-stripe h-2 w-full" />

      <div className="min-w-0 p-4 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-stone-500 sm:text-xs sm:tracking-[0.22em]">
              Compact summary
            </p>
            <h3 className="display-font mt-2 text-xl leading-tight text-stone-950 sm:text-2xl">
              Final risk assessment
            </h3>
          </div>

          <RiskBadge riskLevel={result.risk_level} />
        </div>

        <div className="mt-5 grid min-w-0 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <SummaryTile
            icon={ShieldCheck}
            label="Risk score"
            value={`${result.risk_score}/100`}
          />
          <SummaryTile
            icon={HardHat}
            label="Task intent"
            value={formatTaskIntent(result.task_intent)}
          />
          <SummaryTile
            icon={HardHat}
            label="Professional"
            value={professionalLabel}
          />
          <SummaryTile
            icon={Clock3}
            label="Estimated time"
            value={getDisplayText(result.estimated_time)}
          />
        </div>

        <div className="mt-5 min-w-0 rounded-[20px] border border-stone-200 bg-white p-4 sm:rounded-[24px]">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
            Decision summary
          </p>
          <p className="mt-2 break-words text-sm leading-7 text-stone-700">
            <TypewriterText text={summary} animate={animate} />
          </p>
        </div>

        <div className="mt-5 grid min-w-0 gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
          <div className={`min-w-0 rounded-[20px] border px-4 py-3 sm:rounded-[22px] ${actionButton.panelClassName}`}>
            {isPlanOutdated ? (
              <div className="mb-3 rounded-2xl border border-red-200 bg-white/80 px-3 py-2 text-sm leading-6 text-red-950">
                <p className="font-semibold">
                  Your previous plan may no longer be valid because the risk assessment changed.
                </p>
                {actionPlanInvalidationReason ? (
                  <p className="mt-1 break-words text-xs font-medium">{actionPlanInvalidationReason}</p>
                ) : null}
              </div>
            ) : isPlanActive ? (
              <div className="mb-3 rounded-2xl border border-emerald-200 bg-white/80 px-3 py-2 text-sm font-semibold leading-6 text-emerald-950">
                Plan still appears valid.
              </div>
            ) : null}

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="text-sm font-semibold">{actionButton.heading}</p>
                <p className="text-xs uppercase tracking-[0.16em]">
                  {actionButton.subtext}
                </p>
              </div>
              <button
                type="button"
                onClick={() => void handleActionPlanClick()}
                disabled={isGeneratingPlan || !canGenerateActionPlan}
                className={`inline-flex min-h-11 w-full shrink-0 items-center justify-center gap-2 rounded-full px-4 py-2 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-75 sm:w-auto ${actionButton.buttonClassName}`}
              >
                {isGeneratingPlan ? (
                  <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                ) : (
                  <ClipboardCheck aria-hidden="true" className="h-4 w-4" />
                )}
                {isGeneratingPlan ? actionPlanStatuses[statusIndex] : actionButtonLabel}
              </button>
            </div>
            {planError ? (
              <p className="mt-3 rounded-2xl border border-red-200 bg-red-50 px-3 py-2 text-sm font-semibold leading-6 text-red-900">
                {planError}
              </p>
            ) : null}
          </div>

          <button
            type="button"
            onClick={onOpenDetails}
            className="inline-flex min-h-14 w-full items-center justify-center gap-2 rounded-[20px] border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-950 transition hover:border-amber-300 hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-400 focus:ring-offset-2 sm:rounded-[22px] lg:w-auto"
          >
            View Full Assessment
            <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </button>
        </div>
      </div>

      {isActionPlanOpen && effectiveActionPlan && !isPlanOutdated ? (
        <ActionPlanModal
          plan={effectiveActionPlan}
          onClose={() => setIsActionPlanOpen(false)}
        />
      ) : null}
    </article>
  );
}

function buildActionPlanRequest(
  result: AssessmentResponse,
  request: AssessmentRequest,
): ActionPlanRequest {
  return {
    task_description: request.task_description,
    task_intent: result.task_intent,
    task_category: result.task_category,
    risk_level: result.risk_level,
    risk_score: result.risk_score,
    user_skill_level: request.user_skill_level,
    available_tools: request.available_tools,
    required_tools: result.required_tools,
    required_materials: result.required_materials,
    required_ppe: result.required_ppe,
    safety_warnings: result.safety_warnings,
    recommended_professional_category: result.recommended_professional_category,
    followup_answers: request.answers_to_followups,
  };
}

function getActionPlanButtonConfig(riskLevel: RiskLevel): {
  label: string;
  heading: string;
  subtext: string;
  panelClassName: string;
  buttonClassName: string;
} {
  if (riskLevel === "Safe DIY") {
    return {
      label: "Generate Safe Work Plan",
      heading: "Safe next step available",
      subtext: "Risk-gated plan with PPE and stop conditions",
      panelClassName: "border-emerald-200 bg-emerald-50 text-emerald-950",
      buttonClassName: "bg-emerald-700 hover:bg-emerald-800",
    };
  }

  if (riskLevel === "DIY with supervision") {
    return {
      label: "Generate Supervised Work Plan",
      heading: "Supervised next step available",
      subtext: "Guided plan with extra stop conditions",
      panelClassName: "border-sky-200 bg-sky-50 text-sky-950",
      buttonClassName: "bg-sky-700 hover:bg-sky-800",
    };
  }

  if (riskLevel === "Professional recommended") {
    return {
      label: "Generate Preparation Checklist",
      heading: "Preparation checklist available",
      subtext: "No risky execution steps",
      panelClassName: "border-amber-200 bg-amber-50 text-amber-950",
      buttonClassName: "bg-amber-700 hover:bg-amber-800",
    };
  }

  return {
    label: "View Professional Checklist",
    heading: "Professional-only checklist available",
    subtext: "DIY execution steps are blocked",
    panelClassName: "border-red-200 bg-red-50 text-red-950",
    buttonClassName: "bg-red-800 hover:bg-red-900",
  };
}

function SummaryTile({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof ShieldCheck;
  label: string;
  value: string;
}): JSX.Element {
  return (
    <div className="min-w-0 rounded-[20px] border border-stone-200 bg-white p-4">
      <Icon aria-hidden="true" className="h-4 w-4 text-amber-800" />
      <p className="mt-3 text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
        {label}
      </p>
      <p className="mt-2 break-words text-sm font-bold leading-6 text-stone-950">{value}</p>
    </div>
  );
}
