import type { RiskLevel, RiskScoreBreakdown as RiskScoreBreakdownData } from "../types/assessment";

interface RiskScoreBreakdownProps {
  breakdown: RiskScoreBreakdownData;
  finalRiskLevel: RiskLevel;
}

export function RiskScoreBreakdown({
  breakdown,
  finalRiskLevel,
}: RiskScoreBreakdownProps): JSX.Element {
  const sections = [
    {
      key: "base",
      label: "Base task risk",
      value: breakdown.base_task_risk,
    },
    {
      key: "hazard",
      label: "Hazard severity",
      value: breakdown.hazard_severity,
    },
    {
      key: "skill",
      label: "Skill mismatch",
      value: breakdown.skill_mismatch,
    },
    {
      key: "readiness",
      label: "Tools / PPE readiness",
      value: breakdown.tools_ppe_readiness,
    },
    {
      key: "environment",
      label: "Environment / urgency / unknowns",
      value: breakdown.environment_urgency_unknowns,
    },
  ];

  const wasEscalated = breakdown.threshold_label !== finalRiskLevel;

  return (
    <div className="min-w-0 space-y-4">
      <div className="grid min-w-0 gap-3 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="min-w-0 rounded-[20px] border border-amber-200 bg-amber-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-900">
            Rubric used
          </p>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-stone-700">
            <li><span className="font-semibold text-stone-900">0-20</span>: Safe DIY</li>
            <li><span className="font-semibold text-stone-900">21-40</span>: DIY with supervision</li>
            <li><span className="font-semibold text-stone-900">41-60</span>: Professional recommended</li>
            <li><span className="font-semibold text-stone-900">61-80</span>: Professional required</li>
            <li><span className="font-semibold text-stone-900">81-100</span>: Dangerous / permit-required / do not attempt</li>
          </ul>
        </div>

        <div className="min-w-0 rounded-[20px] border border-stone-200 bg-white p-4">
          <div className="flex flex-wrap items-center gap-3">
            <p className="break-words text-sm font-semibold text-stone-900">
              Total: {breakdown.total}/100
            </p>
            <span className="max-w-full break-words rounded-full bg-stone-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] text-stone-700 sm:tracking-[0.16em]">
              Score tier: {breakdown.threshold_label}
            </span>
            <span className="max-w-full break-words rounded-full bg-stone-950 px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] text-white sm:tracking-[0.16em]">
              Final: {finalRiskLevel}
            </span>
          </div>

          {wasEscalated ? (
            <p className="mt-3 break-words text-sm leading-6 text-red-700">
              The numeric score maps to <span className="font-semibold">{breakdown.threshold_label}</span>, but a safety override escalated the final result to <span className="font-semibold">{finalRiskLevel}</span>.
            </p>
          ) : (
            <p className="mt-3 break-words text-sm leading-6 text-stone-600">
              The final risk level matches the rubric tier from the 100-point score.
            </p>
          )}
        </div>
      </div>

      <div className="grid min-w-0 gap-3 lg:grid-cols-2">
        {sections.map((section) => (
          <div
            key={section.key}
            className="min-w-0 rounded-[20px] border border-stone-200 bg-white p-4"
          >
            <div className="flex items-center justify-between gap-3">
              <p className="min-w-0 break-words text-sm font-semibold text-stone-900">{section.label}</p>
              <p className="text-sm font-bold text-amber-800">
                {section.value.points}/{section.value.max}
              </p>
            </div>
            <p className="mt-2 break-words text-sm leading-6 text-stone-600">
              {section.value.reason}
            </p>
          </div>
        ))}
      </div>

      <div className="min-w-0 rounded-[20px] border border-stone-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
          Safety overrides applied
        </p>
        {breakdown.safety_overrides_applied.length > 0 ? (
          <ul className="mt-3 space-y-2">
            {breakdown.safety_overrides_applied.map((override) => (
              <li
                key={override}
                className="break-words rounded-2xl bg-red-50 px-3 py-2 text-sm leading-6 text-red-900"
              >
                {override}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-stone-500">
            No safety override was needed for this assessment.
          </p>
        )}
      </div>
    </div>
  );
}
