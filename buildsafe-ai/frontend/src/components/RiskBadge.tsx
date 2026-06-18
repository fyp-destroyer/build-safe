import {
  AlertTriangle,
  CheckCircle2,
  HardHat,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";

import type { RiskLevel } from "../types/assessment";

interface RiskBadgeProps {
  riskLevel: RiskLevel;
}

const riskStyles: Record<RiskLevel, string> = {
  "Safe DIY": "border-emerald-300 bg-emerald-50 text-emerald-900",
  "DIY with supervision": "border-sky-300 bg-sky-50 text-sky-900",
  "Professional recommended": "border-amber-300 bg-amber-50 text-amber-900",
  "Professional required": "border-orange-300 bg-orange-50 text-orange-900",
  "Dangerous / permit-required / do not attempt":
    "border-red-400 bg-red-100 text-red-950",
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
      className={`inline-flex max-w-full items-start gap-2 rounded-full border px-3.5 py-2 text-sm font-semibold leading-5 shadow-sm ${riskStyles[riskLevel]}`}
    >
      <Icon aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
      <span className="min-w-0 whitespace-normal break-words">{riskLevel}</span>
    </span>
  );
}
