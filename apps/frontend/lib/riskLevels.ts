import type { ComponentType, SVGProps } from "react";
import {
  IconCheckCircle,
  IconUsers,
  IconAlertTriangle,
  IconShieldAlert,
  IconOctagonAlert,
} from "./icons";

export type RiskLevel = 1 | 2 | 3 | 4 | 5;

interface RiskLevelDef {
  level: RiskLevel;
  label: string;
  colorVar: string;
  textVar: string;
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
}

// Locked — never reassign colors/icons, never reorder. See design.md §4.2.
export const RISK_LEVELS: Record<RiskLevel, RiskLevelDef> = {
  1: {
    level: 1,
    label: "Safe DIY",
    colorVar: "var(--risk-1)",
    textVar: "var(--color-text-primary)",
    Icon: IconCheckCircle,
  },
  2: {
    level: 2,
    label: "DIY with Supervision",
    colorVar: "var(--risk-2)",
    textVar: "var(--color-text-primary)",
    Icon: IconUsers,
  },
  3: {
    level: 3,
    label: "Professional Recommended",
    colorVar: "var(--risk-3)",
    textVar: "var(--color-text-primary)",
    Icon: IconAlertTriangle,
  },
  4: {
    level: 4,
    label: "Professional Required",
    colorVar: "var(--risk-4)",
    textVar: "#fff",
    Icon: IconShieldAlert,
  },
  5: {
    level: 5,
    label: "Dangerous / Do Not Attempt",
    colorVar: "var(--risk-5)",
    textVar: "#fff",
    Icon: IconOctagonAlert,
  },
};
