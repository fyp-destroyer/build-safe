import { RISK_LEVELS, type RiskLevel } from "@/lib/riskLevels";

const SIZES = {
  sm: { pad: "4px 10px 4px 8px", font: "12px", icon: 14 },
  md: { pad: "6px 14px 6px 10px", font: "13px", icon: 16 },
  xl: { pad: "14px 24px 14px 16px", font: "22px", icon: 26 },
} as const;

// Risk level is always conveyed via icon + text + color together, never
// color alone (design.md §13 / root CLAUDE.md accessibility baseline).
export function RiskChip({
  level,
  size = "md",
  showLabel = true,
}: {
  level: RiskLevel;
  size?: keyof typeof SIZES;
  showLabel?: boolean;
}) {
  const def = RISK_LEVELS[level];
  const s = SIZES[size];
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full font-semibold"
      style={{ background: def.colorVar, color: def.textVar, padding: s.pad, fontSize: s.font }}
    >
      <def.Icon width={s.icon} height={s.icon} className="shrink-0" />
      {showLabel && <span>{def.label}</span>}
    </span>
  );
}
