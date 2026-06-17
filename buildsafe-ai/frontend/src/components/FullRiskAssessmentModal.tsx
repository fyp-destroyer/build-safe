import {
  BriefcaseBusiness,
  Calculator,
  CircleHelp,
  ClipboardList,
  Clock3,
  DollarSign,
  HardHat,
  MessageSquareMore,
  Package,
  ScrollText,
  ShieldCheck,
  TriangleAlert,
  Wrench,
  X,
} from "lucide-react";
import { useEffect, type ReactNode } from "react";

import type {
  AssessmentRequest,
  AssessmentResponse,
  FollowupPlanResponse,
} from "../types/assessment";
import { DeveloperTracePanel } from "./DeveloperTracePanel";
import { RiskBadge } from "./RiskBadge";
import { RiskScoreBreakdown } from "./RiskScoreBreakdown";
import {
  formatTaskIntent,
  getDecisionSummary,
  getDisplayList,
  getDisplayText,
  getNextSteps,
  getProfessionalLabel,
} from "./riskAssessmentUtils";

interface FullRiskAssessmentModalProps {
  result: AssessmentResponse;
  request: AssessmentRequest;
  plan: FollowupPlanResponse | null;
  onClose: () => void;
}

export function FullRiskAssessmentModal({
  result,
  request,
  plan,
  onClose,
}: FullRiskAssessmentModalProps): JSX.Element {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const tools = getDisplayList(result.required_tools);
  const materials = getDisplayList(result.required_materials);
  const ppe = getDisplayList(result.required_ppe);
  const warnings = getDisplayList(result.safety_warnings);
  const rulesTriggered = getDisplayList(result.rules_triggered);
  const riskFactors = getDisplayList(plan?.risk_factors);
  const unknowns = getDisplayList(plan?.critical_missing_info);
  const askedQuestions = Object.keys(request.answers_to_followups);
  const answerEntries = Object.entries(request.answers_to_followups).filter(([, answer]) =>
    typeof answer === "string" ? answer.trim().length > 0 : Boolean(answer),
  );
  const decisionSummary = getDecisionSummary(result);
  const nextSteps = getNextSteps(result);
  const professionalLabel = getProfessionalLabel(result);
  const interpretation = getDisplayText(plan?.selected_interpretation, "No special interpretation notes");

  return (
    <div
      className="fixed inset-0 z-50 bg-stone-950/55 p-4 backdrop-blur-sm sm:p-6"
      onClick={onClose}
      role="presentation"
    >
      <div className="flex h-full items-start justify-center">
        <div
          className="flex max-h-full w-full max-w-6xl flex-col overflow-hidden rounded-[32px] border border-stone-200 bg-[linear-gradient(180deg,#fffdf9_0%,#ffffff_24%,#f4efe6_100%)] shadow-[0_36px_120px_rgba(28,25,23,0.34)]"
          onClick={(event) => event.stopPropagation()}
          role="dialog"
          aria-modal="true"
          aria-labelledby="full-assessment-title"
        >
          <div className="hazard-stripe h-2 w-full" />

          <header className="shrink-0 border-b border-stone-200 bg-white/90 px-5 py-5 sm:px-7">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-amber-700">
                  Full risk assessment
                </p>
                <h2
                  id="full-assessment-title"
                  className="display-font mt-2 text-3xl leading-tight text-stone-950"
                >
                  {request.task_description}
                </h2>
                <p className="mt-3 max-w-3xl text-sm leading-7 text-stone-600">
                  {getDisplayText(result.explanation)}
                </p>
              </div>

              <button
                type="button"
                onClick={onClose}
                className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-stone-200 bg-stone-50 text-stone-700 transition hover:border-stone-300 hover:bg-stone-100"
                aria-label="Close full assessment"
              >
                <X aria-hidden="true" className="h-5 w-5" />
              </button>
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-3">
              <RiskBadge riskLevel={result.risk_level} />
              <HeaderStat label="Risk score" value={`${result.risk_score}/100`} />
              <HeaderStat label="Estimated time" value={getDisplayText(result.estimated_time)} />
              <HeaderStat label="Estimated cost" value={getDisplayText(result.estimated_cost_range)} />
              <HeaderStat
                label="Confidence"
                value={`${Math.round(result.confidence_score * 100)}%`}
              />
            </div>
          </header>

          <div className="flex-1 overflow-y-auto px-5 py-5 sm:px-7 sm:py-6">
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
              <SectionCard icon={ClipboardList} title="Header section">
                <div className="grid gap-3 md:grid-cols-2">
                  <KeyValue label="Task intent" value={formatTaskIntent(result.task_intent)} />
                  <KeyValue label="Task category" value={getDisplayText(result.task_category)} />
                  <KeyValue label="Short explanation" value={decisionSummary} />
                  <KeyValue label="Assessment interpretation" value={interpretation} />
                </div>
              </SectionCard>

              <SectionCard icon={BriefcaseBusiness} title="Professional recommendation">
                <div className="rounded-[22px] border border-amber-200 bg-amber-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-900">
                    Recommended category
                  </p>
                  <p className="mt-2 text-lg font-bold text-stone-950">{professionalLabel}</p>
                </div>
                <p className="mt-4 text-sm leading-7 text-stone-700">
                  {getProfessionalReason(result.risk_level)}
                </p>
              </SectionCard>
            </div>

            <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <SectionCard icon={ShieldCheck} title="Decision section">
                <div className="grid gap-3 md:grid-cols-3">
                  <KeyValue label="Final decision" value={result.risk_level} />
                  <KeyValue label="Why this task stands out" value={decisionSummary} />
                  <KeyValue label="What you should do next" value={nextSteps[0] ?? "Not available"} />
                </div>

                <ListBlock
                  title="Recommended next steps"
                  items={nextSteps}
                  emptyLabel="No extra next steps were returned."
                  tone="default"
                  className="mt-4"
                />
              </SectionCard>

              <SectionCard icon={TriangleAlert} title="Safety warnings">
                <ListBlock
                  items={warnings}
                  emptyLabel="No specific safety warnings were returned for this assessment."
                  tone="warning"
                />
              </SectionCard>
            </div>

            <SectionCard icon={Calculator} title="Risk score breakdown" className="mt-4">
              <RiskScoreBreakdown
                breakdown={result.risk_score_breakdown}
                finalRiskLevel={result.risk_level}
              />
            </SectionCard>

            <SectionCard icon={Wrench} title="Tools and materials" className="mt-4">
              <div className="grid gap-4 lg:grid-cols-3">
                <ChipSection title="Required tools" icon={Wrench} items={tools} emptyLabel="No tool list returned." />
                <ChipSection
                  title="Required materials"
                  icon={Package}
                  items={materials}
                  emptyLabel="No materials list returned."
                />
                <ChipSection title="Required PPE" icon={HardHat} items={ppe} emptyLabel="No PPE list returned." />
              </div>
            </SectionCard>

            <SectionCard icon={MessageSquareMore} title="Follow-up questions and assumptions" className="mt-4">
              <div className="grid gap-4 xl:grid-cols-2">
                <ListBlock
                  title="Risk factors"
                  items={riskFactors}
                  emptyLabel="No separate risk factors were returned."
                />
                <ListBlock
                  title="Important unknowns"
                  items={unknowns}
                  emptyLabel="No critical unknowns remained."
                />
              </div>

              <div className="mt-4 grid gap-4 xl:grid-cols-2">
                <ListBlock
                  title="Questions asked"
                  items={askedQuestions}
                  emptyLabel="No follow-up questions were needed."
                />
                <AnswerList
                  entries={answerEntries}
                  emptyLabel="No follow-up answers were stored for this assessment."
                />
              </div>
            </SectionCard>

            <SectionCard icon={ScrollText} title="Rules triggered" className="mt-4">
              <ListBlock
                items={rulesTriggered}
                emptyLabel="No specific rules were triggered."
              />
            </SectionCard>

            <SectionCard icon={CircleHelp} title="Assessment signals" className="mt-4">
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <SignalTile icon={Clock3} label="Estimated time" value={getDisplayText(result.estimated_time)} />
                <SignalTile icon={DollarSign} label="Estimated cost" value={getDisplayText(result.estimated_cost_range)} />
                <SignalTile
                  icon={ClipboardList}
                  label="Task category"
                  value={getDisplayText(result.task_category)}
                />
                <SignalTile
                  icon={ShieldCheck}
                  label="Task intent"
                  value={formatTaskIntent(result.task_intent)}
                />
              </div>
            </SectionCard>

            <DeveloperTracePanel trace={result.debug_trace} />
          </div>
        </div>
      </div>
    </div>
  );
}

function SectionCard({
  icon: Icon,
  title,
  children,
  className = "",
}: {
  icon: typeof ClipboardList;
  title: string;
  children: ReactNode;
  className?: string;
}): JSX.Element {
  return (
    <section className={`rounded-[26px] border border-stone-200 bg-white p-5 shadow-sm ${className}`}>
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-amber-100 text-amber-900">
          <Icon aria-hidden="true" className="h-5 w-5" />
        </div>
        <h3 className="text-lg font-bold text-stone-950">{title}</h3>
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function HeaderStat({
  label,
  value,
}: {
  label: string;
  value: string;
}): JSX.Element {
  return (
    <div className="rounded-full border border-stone-200 bg-stone-50 px-4 py-2">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-stone-500">
        {label}
      </p>
      <p className="mt-1 text-sm font-bold text-stone-900">{value}</p>
    </div>
  );
}

function KeyValue({
  label,
  value,
}: {
  label: string;
  value: string;
}): JSX.Element {
  return (
    <div className="rounded-[20px] border border-stone-200 bg-stone-50 p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
        {label}
      </p>
      <p className="mt-2 text-sm leading-6 text-stone-800">{value}</p>
    </div>
  );
}

function ChipSection({
  title,
  icon: Icon,
  items,
  emptyLabel,
}: {
  title: string;
  icon: typeof Wrench;
  items: string[];
  emptyLabel: string;
}): JSX.Element {
  return (
    <div className="rounded-[22px] border border-stone-200 bg-stone-50 p-4">
      <div className="flex items-center gap-3">
        <Icon aria-hidden="true" className="h-4 w-4 text-amber-800" />
        <h4 className="text-sm font-bold text-stone-950">{title}</h4>
      </div>

      {items.length > 0 ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {items.map((item) => (
            <span
              key={`${title}-${item}`}
              className="rounded-full border border-stone-200 bg-white px-3 py-2 text-sm text-stone-700"
            >
              {item}
            </span>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-stone-500">{emptyLabel}</p>
      )}
    </div>
  );
}

function ListBlock({
  title,
  items,
  emptyLabel,
  tone = "default",
  className = "",
}: {
  title?: string;
  items: string[];
  emptyLabel: string;
  tone?: "default" | "warning";
  className?: string;
}): JSX.Element {
  return (
    <div className={className}>
      {title ? (
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
          {title}
        </p>
      ) : null}

      {items.length > 0 ? (
        <ul className={title ? "mt-3 space-y-2" : "space-y-2"}>
          {items.map((item) => (
            <li
              key={`${title ?? "item"}-${item}`}
              className={`rounded-2xl px-3 py-2 text-sm leading-6 ${
                tone === "warning"
                  ? "bg-red-50 text-red-900"
                  : "bg-stone-50 text-stone-700"
              }`}
            >
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className={title ? "mt-3 text-sm text-stone-500" : "text-sm text-stone-500"}>
          {emptyLabel}
        </p>
      )}
    </div>
  );
}

function AnswerList({
  entries,
  emptyLabel,
}: {
  entries: Array<[string, unknown]>;
  emptyLabel: string;
}): JSX.Element {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
        Your answers
      </p>

      {entries.length > 0 ? (
        <div className="mt-3 space-y-3">
          {entries.map(([question, answer]) => (
            <div
              key={question}
              className="rounded-[20px] border border-stone-200 bg-stone-50 p-4"
            >
              <p className="text-sm font-semibold text-stone-900">{question}</p>
              <p className="mt-2 text-sm leading-6 text-stone-700">
                {typeof answer === "string" ? answer : String(answer)}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-stone-500">{emptyLabel}</p>
      )}
    </div>
  );
}

function SignalTile({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Clock3;
  label: string;
  value: string;
}): JSX.Element {
  return (
    <div className="rounded-[20px] border border-stone-200 bg-stone-50 p-4">
      <Icon aria-hidden="true" className="h-4 w-4 text-amber-800" />
      <p className="mt-3 text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
        {label}
      </p>
      <p className="mt-2 text-sm font-semibold leading-6 text-stone-900">{value}</p>
    </div>
  );
}

function getProfessionalReason(riskLevel: AssessmentResponse["risk_level"]): string {
  if (riskLevel === "Safe DIY" || riskLevel === "DIY with supervision") {
    return "No specialist is required based on the current assessment, provided the user follows the listed controls, PPE, and site checks.";
  }

  if (riskLevel === "Professional recommended") {
    return "A qualified trade professional is strongly advised because the task carries meaningful electrical, structural, or hazard-management risk.";
  }

  if (riskLevel === "Professional required") {
    return "This task has crossed the threshold where professional handling is the safest recommendation and should not be treated as routine DIY.";
  }

  return "This task presents severe safety, structural, utility, or permitting concerns and should not be attempted without qualified professional control.";
}
