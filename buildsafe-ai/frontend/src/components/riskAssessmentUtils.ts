import type {
  AssessmentResponse,
  RiskLevel,
  TaskIntent,
} from "../types/assessment";

const fallbackDecisionSummaries: Record<RiskLevel, string> = {
  "Safe DIY":
    "This task may be suitable for DIY if the user follows the listed PPE, materials, and safety controls.",
  "DIY with supervision":
    "This task may be manageable with oversight, but it still carries enough risk to justify extra checks before work starts.",
  "Professional recommended":
    "The task has meaningful risk signals, so a qualified trade professional is strongly recommended before attempting it.",
  "Professional required":
    "The task crosses the threshold where professional handling is the safest recommendation.",
  "Dangerous / permit-required / do not attempt":
    "The task presents serious structural, utility, permitting, or injury concerns and should not be attempted as DIY.",
};

const taskIntentLabels: Record<TaskIntent, string> = {
  hanging_wall_decor: "Hanging wall decor",
  wall_painting: "Wall painting",
  electrical_fixture_installation: "Electrical fixture installation",
  electrical_wiring_repair: "Electrical wiring repair",
  plumbing_leak_repair: "Plumbing leak repair",
  wall_demolition: "Wall demolition",
  tile_installation: "Tile installation",
  furniture_assembly: "Furniture assembly",
  shelf_installation: "Shelf installation",
  light_bulb_replacement: "Light bulb replacement",
  ceiling_fan_installation: "Ceiling fan installation",
  hvac_repair: "HVAC repair",
  general_diy: "General DIY task",
};

export function getDecisionSummary(
  result: Pick<AssessmentResponse, "risk_level" | "explanation">,
): string {
  return getFirstSentence(result.explanation) ?? fallbackDecisionSummaries[result.risk_level];
}

export function getCompactSummary(
  result: Pick<AssessmentResponse, "risk_level" | "explanation">,
): string {
  return truncateText(getDecisionSummary(result), 150);
}

export function formatTaskIntent(taskIntent: TaskIntent | string | null | undefined): string {
  if (!taskIntent) {
    return "Not available";
  }

  if (taskIntent in taskIntentLabels) {
    return taskIntentLabels[taskIntent as TaskIntent];
  }

  return taskIntent
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function getProfessionalLabel(result: AssessmentResponse): string {
  const normalized = result.recommended_professional_category?.trim();
  if (normalized) {
    return normalized;
  }

  return needsProfessional(result.risk_level) ? "Recommended but not specified" : "Not required";
}

export function getNextSteps(result: AssessmentResponse): string[] {
  if (result.follow_up_questions.length > 0) {
    return result.follow_up_questions;
  }

  if (needsProfessional(result.risk_level)) {
    return [
      "Pause before starting and arrange a qualified inspection or trade professional.",
      "Confirm permits, shutdown procedures, and site hazards before work begins.",
    ];
  }

  return [
    "Gather the listed PPE, tools, and materials before starting.",
    "Re-check the site for hidden hazards and stop if conditions change.",
  ];
}

export function getDisplayText(
  value: string | null | undefined,
  fallback = "Not available",
): string {
  const normalized = value?.trim();
  return normalized ? normalized : fallback;
}

export function getDisplayList(items: string[] | null | undefined): string[] {
  return (items ?? []).map((item) => item.trim()).filter(Boolean);
}

export function needsProfessional(riskLevel: RiskLevel): boolean {
  return (
    riskLevel === "Professional recommended" ||
    riskLevel === "Professional required" ||
    riskLevel === "Dangerous / permit-required / do not attempt"
  );
}

function getFirstSentence(value: string | null | undefined): string | null {
  const normalized = value?.trim();
  if (!normalized) {
    return null;
  }

  const match = normalized.match(/^.+?[.!?](?:\s|$)/);
  return match ? match[0].trim() : normalized;
}

function truncateText(value: string, maxLength: number): string {
  if (value.length <= maxLength) {
    return value;
  }

  return `${value.slice(0, maxLength - 1).trimEnd()}...`;
}
