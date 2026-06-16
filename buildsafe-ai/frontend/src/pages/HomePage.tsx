import { AlertOctagon, Building2, HardHat, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { AdminSeedDataPanel } from "../components/AdminSeedDataPanel";
import { AssessmentForm } from "../components/AssessmentForm";
import { ResultCard } from "../components/ResultCard";
import { assessTask } from "../services/api";
import type { AssessmentRequest, AssessmentResponse } from "../types/assessment";

const riskTiers = [
  "Safe DIY",
  "DIY with supervision",
  "Professional recommended",
  "Professional required",
  "Do not attempt",
];

export function HomePage(): JSX.Element {
  const [result, setResult] = useState<AssessmentResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAssessTask(payload: AssessmentRequest): Promise<void> {
    setIsSubmitting(true);
    setError(null);

    try {
      const assessment = await assessTask(payload);
      setResult(assessment);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Assessment failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#f7f7f5] text-zinc-950">
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-5 px-4 py-6 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-md bg-zinc-950 text-white">
              <HardHat aria-hidden="true" className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-normal text-zinc-950">BuildSafe AI</h1>
              <p className="mt-1 text-sm font-medium text-zinc-600">Construction safety triage and DIY risk assessment</p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {riskTiers.map((tier) => (
              <span key={tier} className="rounded-md border border-zinc-200 bg-zinc-50 px-2.5 py-1 text-xs font-semibold text-zinc-700">
                {tier}
              </span>
            ))}
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[420px_minmax(0,1fr)] lg:px-8">
        <section className="rounded-md border border-zinc-200 bg-white p-6 shadow-panel">
          <div className="mb-6 flex items-start gap-3 border-b border-zinc-200 pb-5">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-amber-100 text-amber-800">
              <ShieldCheck aria-hidden="true" className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-zinc-950">Task Intake</h2>
              <p className="mt-1 text-sm leading-6 text-zinc-600">Enter the work scope and site context for a safety-first assessment.</p>
            </div>
          </div>

          <AssessmentForm isSubmitting={isSubmitting} onSubmit={handleAssessTask} />

          {error ? (
            <div className="mt-5 flex gap-3 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
              <AlertOctagon aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
              <span className="break-words">{error}</span>
            </div>
          ) : null}
        </section>

        <div className="space-y-6">
          <section className="grid gap-4 sm:grid-cols-3">
            <StatusPanel icon={Building2} label="Scope" value="Home, shop, office" />
            <StatusPanel icon={ShieldCheck} label="Mode" value="Rule-based MVP" />
            <StatusPanel icon={HardHat} label="Output" value="Risk tier + trade referral" />
          </section>

          <ResultCard result={result} />
          <AdminSeedDataPanel />
        </div>
      </main>
    </div>
  );
}

interface StatusPanelProps {
  icon: typeof Building2;
  label: string;
  value: string;
}

function StatusPanel({ icon: Icon, label, value }: StatusPanelProps): JSX.Element {
  return (
    <div className="flex min-h-24 gap-3 rounded-md border border-zinc-200 bg-white p-4 shadow-panel">
      <Icon aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-teal-700" />
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-[0.08em] text-zinc-500">{label}</p>
        <p className="mt-2 break-words text-sm font-bold text-zinc-900">{value}</p>
      </div>
    </div>
  );
}
