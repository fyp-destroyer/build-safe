import {
  AlertTriangle,
  CheckSquare,
  Clock3,
  DollarSign,
  HardHat,
  HelpCircle,
  ShieldCheck,
  Sparkles,
  Wrench,
} from "lucide-react";
import type { ReactNode } from "react";

import type { AssessmentResponse } from "../types/assessment";
import { RiskBadge } from "./RiskBadge";

interface ResultCardProps {
  result: AssessmentResponse | null;
}

export function ResultCard({ result }: ResultCardProps): JSX.Element {
  if (!result) {
    return (
      <section className="rounded-md border border-dashed border-zinc-300 bg-white p-6 shadow-panel">
        <div className="hazard-stripe h-2 rounded-sm" />
        <div className="mt-6 flex items-start gap-3">
          <ShieldCheck aria-hidden="true" className="mt-1 h-6 w-6 text-teal-700" />
          <div>
            <h2 className="text-lg font-semibold text-zinc-900">Risk report</h2>
            <p className="mt-2 text-sm leading-6 text-zinc-600">
              Submit a task to generate the decision, reasoning, equipment checklist, trade referral, and follow-up checks.
            </p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <article className="rounded-md border border-zinc-200 bg-white shadow-panel">
      <header className="border-b border-zinc-200 p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <p className="text-sm font-semibold uppercase tracking-[0.08em] text-zinc-500">{result.task_category}</p>
            <h2 className="mt-2 text-2xl font-bold text-zinc-950">Supervisor Demo Risk Report</h2>
          </div>
          <RiskBadge riskLevel={result.risk_level} />
        </div>

        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          <Metric label="Risk score" value={`${result.risk_score}/100`} />
          <Metric label="Confidence" value={`${Math.round(result.confidence_score * 100)}%`} />
          <Metric label="Rules matched" value={`${result.rules_triggered.length}`} />
        </div>
      </header>

      <div className="divide-y divide-zinc-200">
        <ReportSection icon={ShieldCheck} title="Decision">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-zinc-900">{result.risk_level}</p>
              <p className="mt-1 text-sm leading-6 text-zinc-600">
                Category: {result.task_category}. Confidence: {Math.round(result.confidence_score * 100)}%.
              </p>
            </div>
            <RiskBadge riskLevel={result.risk_level} />
          </div>
        </ReportSection>

        <ReportSection icon={AlertTriangle} title="Why this is risky/safe">
          <p className="text-sm leading-6 text-zinc-700">{result.explanation}</p>
          <BulletList
            items={result.safety_warnings}
            emptyLabel="No urgent warnings were returned for this assessment."
            tone="warning"
          />
          <TechnicalRules rules={result.rules_triggered} />
        </ReportSection>

        <ReportSection icon={Wrench} title="Required tools">
          <BulletList items={result.required_tools} emptyLabel="No special tools listed." />
        </ReportSection>

        <ReportSection icon={Sparkles} title="Required materials">
          <BulletList items={result.required_materials} emptyLabel="No special materials listed." />
        </ReportSection>

        <ReportSection icon={CheckSquare} title="PPE checklist">
          <ul className="mt-1 grid gap-2 sm:grid-cols-2">
            {result.required_ppe.map((item) => (
              <li key={item} className="flex items-start gap-2 text-sm text-zinc-700">
                <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border border-zinc-300 bg-zinc-50" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </ReportSection>

        <ReportSection icon={HardHat} title="Professional recommendation">
          <p className="text-sm font-semibold text-zinc-900">{result.recommended_professional_category}</p>
        </ReportSection>

        <ReportSection icon={Clock3} title="Estimated time and cost">
          <div className="grid gap-4 sm:grid-cols-2">
            <InfoLine icon={Clock3} label="Estimated time" value={result.estimated_time} />
            <InfoLine icon={DollarSign} label="Estimated cost" value={result.estimated_cost_range} />
          </div>
        </ReportSection>

        <ReportSection icon={HelpCircle} title="Follow-up questions">
          <BulletList items={result.follow_up_questions} emptyLabel="No follow-up questions needed." />
        </ReportSection>
      </div>
    </article>
  );
}

interface ReportSectionProps {
  icon: typeof ShieldCheck;
  title: string;
  children: ReactNode;
}

function ReportSection({ icon: Icon, title, children }: ReportSectionProps): JSX.Element {
  return (
    <section className="p-6">
      <div className="mb-4 flex items-center gap-3">
        <Icon aria-hidden="true" className="h-5 w-5 shrink-0 text-teal-700" />
        <h3 className="text-base font-bold text-zinc-950">{title}</h3>
      </div>
      {children}
    </section>
  );
}

interface BulletListProps {
  items: string[];
  emptyLabel: string;
  tone?: "default" | "warning";
}

function BulletList({ items, emptyLabel, tone = "default" }: BulletListProps): JSX.Element {
  if (items.length === 0) {
    return <p className="text-sm text-zinc-500">{emptyLabel}</p>;
  }

  const markerClass = tone === "warning" ? "bg-amber-500" : "bg-teal-600";

  return (
    <ul className="mt-3 space-y-2">
      {items.map((item) => (
        <li key={item} className="flex items-start gap-2 text-sm leading-6 text-zinc-700">
          <span className={`mt-2 h-1.5 w-1.5 shrink-0 rounded-full ${markerClass}`} />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

interface TechnicalRulesProps {
  rules: string[];
}

function TechnicalRules({ rules }: TechnicalRulesProps): JSX.Element | null {
  if (rules.length === 0) {
    return null;
  }

  return (
    <details className="mt-4 rounded-md border border-zinc-200 bg-zinc-50 px-4 py-3">
      <summary className="cursor-pointer text-sm font-semibold text-zinc-800">Rules triggered</summary>
      <ul className="mt-3 space-y-2">
        {rules.map((rule) => (
          <li key={rule} className="text-sm leading-6 text-zinc-600">
            {rule}
          </li>
        ))}
      </ul>
    </details>
  );
}

interface MetricProps {
  label: string;
  value: string;
}

function Metric({ label, value }: MetricProps): JSX.Element {
  return (
    <div className="border-l-2 border-amber-500 pl-3">
      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-zinc-500">{label}</p>
      <p className="mt-1 break-words text-lg font-bold text-zinc-950">{value}</p>
    </div>
  );
}

interface InfoLineProps {
  icon: typeof Clock3;
  label: string;
  value: string;
}

function InfoLine({ icon: Icon, label, value }: InfoLineProps): JSX.Element {
  return (
    <div className="flex gap-3">
      <Icon aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-[0.08em] text-zinc-500">{label}</p>
        <p className="mt-1 break-words text-sm font-medium text-zinc-800">{value}</p>
      </div>
    </div>
  );
}
