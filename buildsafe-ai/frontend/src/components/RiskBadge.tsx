import { AlertTriangle, CheckCircle2, HardHat, ShieldAlert, ShieldCheck } from "lucide-react";

import type { RiskLevel } from "../types/assessment";

interface RiskBadgeProps {
  riskLevel: RiskLevel;
}

const riskStyles: Record<RiskLevel, string> = {
  "Safe DIY": "border-emerald-300 bg-emerald-50 text-emerald-800",
  "DIY with supervision": "border-teal-300 bg-teal-50 text-teal-800",
  "Professional recommended": "border-amber-300 bg-amber-50 text-amber-900",
  "Professional required": "border-orange-300 bg-orange-50 text-orange-900",
  "Dangerous / permit-required / do not attempt": "border-red-300 bg-red-50 text-red-800",
};

const riskIcons: Record<RiskLevel, typeof CheckCircle2> = {
  "Safe DIY": CheckCircle2,
  "DIY with supervision": ShieldCheck,
  "Professional recommended": HardHat,
  "Professional required": ShieldAlert,
  "Dangerous / permit-required / do not attempt": AlertTriangle,
};

export function RiskBadge({ riskLevel }: RiskBadgeProps): JSX.Element {
  const Icon = riskIcons[riskLevel];

  return (
    <span
      className={`inline-flex max-w-full items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-semibold ${riskStyles[riskLevel]}`}
    >
      <Icon aria-hidden="true" className="h-4 w-4 shrink-0" />
      <span className="break-words">{riskLevel}</span>
    </span>
  );
}
