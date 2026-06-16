export type SkillLevel = "beginner" | "intermediate" | "expert";
export type LocationType = "house" | "apartment" | "shop" | "office";
export type Urgency = "low" | "medium" | "high" | "emergency";

export type RiskLevel =
  | "Safe DIY"
  | "DIY with supervision"
  | "Professional recommended"
  | "Professional required"
  | "Dangerous / permit-required / do not attempt";

export interface AssessmentRequest {
  task_description: string;
  user_skill_level: SkillLevel;
  available_tools: string[];
  location_type: LocationType;
  urgency: Urgency;
  budget_range: string;
  answers_to_followups: Record<string, string>;
}

export interface AssessmentResponse {
  task_category: string;
  risk_level: RiskLevel;
  risk_score: number;
  confidence_score: number;
  explanation: string;
  follow_up_questions: string[];
  required_tools: string[];
  required_materials: string[];
  required_ppe: string[];
  estimated_time: string;
  estimated_cost_range: string;
  recommended_professional_category: string;
  safety_warnings: string[];
  rules_triggered: string[];
}

export interface SeedDataResponse {
  tools: Record<string, string[]>;
  materials: Record<string, { materials: string[]; ppe: string[] }>;
  safety_rules: Array<{
    id: string;
    description: string;
    category: string;
    keywords: string[];
    min_risk_level: number;
    score_boost: number;
    warning: string;
  }>;
  professional_categories: Record<string, { category: string; optional: string }>;
}
