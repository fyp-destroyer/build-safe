import { AlertTriangle, Clock3, DollarSign, HardHat, ShieldCheck } from "lucide-react";

import type { AssessmentResponse } from "../types/assessment";
import { DetailList } from "./DetailList";
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
            <h2 className="text-lg font-semibold text-zinc-900">Assessment output</h2>
            <p className="mt-2 text-sm leading-6 text-zinc-600">
              Submit a task to generate a risk tier, safety warnings, recommended PPE, materials, tools, trade category, and follow-up checks.
            </p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-md border border-zinc-200 bg-white p-6 shadow-panel">
      <div className="flex flex-col gap-4 border-b border-zinc-200 pb-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.08em] text-zinc-500">{result.task_category}</p>
          <h2 className="mt-2 text-2xl font-bold text-zinc-950">Risk Assessment</h2>
        </div>
        <RiskBadge riskLevel={result.risk_level} />
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-3">
        <Metric label="Risk score" value={`${result.risk_score}/100`} />
        <Metric label="Confidence" value={`${Math.round(result.confidence_score * 100)}%`} />
        <Metric label="Trade category" value={result.recommended_professional_category} />
      </div>

      <div className="mt-6 rounded-md border border-zinc-200 bg-zinc-50 p-4">
        <p className="text-sm leading-6 text-zinc-700">{result.explanation}</p>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <InfoLine icon={Clock3} label="Estimated time" value={result.estimated_time} />
        <InfoLine icon={DollarSign} label="Estimated cost" value={result.estimated_cost_range} />
      </div>

      <div className="mt-7 grid gap-6 lg:grid-cols-2">
        <DetailList title="Safety warnings" items={result.safety_warnings} emptyLabel="No urgent warnings returned" />
        <DetailList title="Follow-up questions" items={result.follow_up_questions} />
        <DetailList title="Required tools" items={result.required_tools} />
        <DetailList title="Required materials" items={result.required_materials} />
        <DetailList title="Required PPE" items={result.required_ppe} />
        <DetailList title="Rules triggered" items={result.rules_triggered} emptyLabel="No high-risk rules triggered" />
      </div>
    </section>
  );
}

interface MetricProps {
  label: string;
  value: string;
}

function Metric({ label, value }: MetricProps): JSX.Element {
  return (
    <div className="rounded-md border border-zinc-200 bg-white px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-zinc-500">{label}</p>
      <p className="mt-2 break-words text-lg font-bold text-zinc-950">{value}</p>
    </div>
  );
}

interface InfoLineProps {
  icon: typeof AlertTriangle;
  label: string;
  value: string;
}

function InfoLine({ icon: Icon, label, value }: InfoLineProps): JSX.Element {
  return (
    <div className="flex gap-3 rounded-md border border-zinc-200 bg-white px-4 py-3">
      <Icon aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-[0.08em] text-zinc-500">{label}</p>
        <p className="mt-1 break-words text-sm font-medium text-zinc-800">{value}</p>
      </div>
    </div>
  );
}
