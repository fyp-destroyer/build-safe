export type SkillLevel = "beginner" | "intermediate" | "expert";
export type LocationType = "house" | "apartment" | "shop" | "office";
export type Urgency = "low" | "medium" | "high" | "emergency";

export type RiskLevel =
  | "Safe DIY"
  | "DIY with supervision"
  | "Professional recommended"
  | "Professional required"
  | "Dangerous / permit-required / do not attempt";

export type TaskIntent =
  | "hanging_wall_decor"
  | "wall_painting"
  | "electrical_fixture_installation"
  | "electrical_wiring_repair"
  | "plumbing_leak_repair"
  | "wall_demolition"
  | "tile_installation"
  | "furniture_assembly"
  | "shelf_installation"
  | "light_bulb_replacement"
  | "ceiling_fan_installation"
  | "hvac_repair"
  | "general_diy";

export type PlanType =
  | "safe_diy_plan"
  | "supervised_plan"
  | "preparation_checklist"
  | "professional_only_checklist";

export interface AssessmentRequest {
  task_description: string;
  user_skill_level: SkillLevel;
  available_tools: string[];
  location_type: LocationType;
  urgency: Urgency;
  budget_range: string;
  answers_to_followups: Record<string, string>;
}

export interface RiskScoreComponent {
  points: number;
  max: number;
  reason: string;
}

export interface RiskScoreBreakdown {
  base_task_risk: RiskScoreComponent;
  hazard_severity: RiskScoreComponent;
  skill_mismatch: RiskScoreComponent;
  tools_ppe_readiness: RiskScoreComponent;
  environment_urgency_unknowns: RiskScoreComponent;
  total: number;
  threshold_label: RiskLevel;
  safety_overrides_applied: string[];
}

export interface AssessmentResponse {
  task_intent: TaskIntent;
  task_category: string;
  risk_level: RiskLevel;
  risk_score: number;
  risk_score_breakdown: RiskScoreBreakdown;
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
  debug_trace?: DebugTrace | null;
}

export type ActionPlanStatus = "none" | "active" | "outdated";

export interface DetectedAssessmentUpdate {
  field: string;
  old_value_if_known: unknown;
  new_value: unknown;
  confidence: number;
}

export interface UpdateRiskScoreChange {
  old_score: number | null;
  new_score: number | null;
  changed: boolean;
  reason: string;
}

export interface UpdateRiskLevelChange {
  old_level: RiskLevel | string;
  new_level: RiskLevel | string;
  changed: boolean;
  reason: string;
}

export interface UpdateAssessmentChangeSummary {
  detected_updates: DetectedAssessmentUpdate[];
  affected_sections: string[];
  likely_unchanged_sections: string[];
  changed_sections: string[];
  unchanged_sections: string[];
  risk_score_change: UpdateRiskScoreChange | null;
  risk_level_change: UpdateRiskLevelChange | null;
}

export interface ActiveAssessmentSession {
  session_id: string;
  original_task_description: string;
  task_intent: TaskIntent;
  task_category: string;
  followup_answers: Record<string, string>;
  user_skill_level: SkillLevel;
  available_tools: string[];
  location_type: LocationType;
  urgency: Urgency;
  budget_range: string;
  latest_assessment: AssessmentResponse;
  assessment_history: AssessmentResponse[];
  change_summary: UpdateAssessmentChangeSummary | null;
  action_plan: ActionPlanResponse | null;
  action_plan_status: ActionPlanStatus;
  action_plan_invalidated: boolean;
  action_plan_invalidation_reason: string | null;
}

export interface UpdateAssessmentRequest {
  session_id: string;
  previous_assessment: AssessmentResponse;
  task_description: string;
  task_intent: string;
  task_category: string;
  previous_answers: Record<string, unknown>;
  update_message: string;
  current_user_context: Record<string, unknown>;
}

export interface UpdateAssessmentDebugTrace {
  update_flow_used: boolean;
  update_message: string;
  update_parsing_enabled: boolean;
  gemini_enabled: boolean;
  gemini_used: boolean;
  fallback_used: boolean;
  parser_source: string;
  gemini_model: string;
  gemini_error?: string | null;
}

export interface UpdateAssessmentResponse {
  updated_assessment: AssessmentResponse;
  change_summary: UpdateAssessmentChangeSummary;
  assistant_message: string;
  needs_reassessment: boolean;
  requires_more_information: boolean;
  follow_up_questions: string[];
  debug_trace: UpdateAssessmentDebugTrace;
}

export interface ActionPlanRequest {
  task_description: string;
  task_intent: TaskIntent;
  task_category: string;
  risk_level: RiskLevel;
  risk_score: number;
  user_skill_level: SkillLevel;
  available_tools: string[];
  required_tools: string[];
  required_materials: string[];
  required_ppe: string[];
  safety_warnings: string[];
  recommended_professional_category: string;
  followup_answers: Record<string, unknown>;
}

export interface ActionPlanStep {
  step_number: number;
  title: string;
  description: string;
  safety_note: string;
  estimated_time: string;
}

export interface ActionPlanDebugTrace {
  action_plan_generated: boolean;
  plan_type: PlanType;
  llm_used_for_plan: boolean;
  safety_restriction_applied: boolean;
  reason_if_steps_blocked: string;
}

export interface ActionPlanResponse {
  plan_type: PlanType;
  allowed_to_show_steps: boolean;
  title: string;
  summary: string;
  safety_notice: string;
  prerequisites: string[];
  tools_required: string[];
  materials_required: string[];
  ppe_required: string[];
  steps: ActionPlanStep[];
  stop_conditions: string[];
  when_to_call_professional: string[];
  professional_questions: string[];
  disclaimer: string;
  debug_trace?: ActionPlanDebugTrace | null;
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

export interface FollowupPlanRequest {
  task_description: string;
  known_answers: Record<string, string>;
}

export interface FollowupPlanResponse {
  task_intent: TaskIntent;
  task_category: string;
  is_ambiguous: boolean;
  possible_interpretations: string[];
  selected_interpretation: string;
  risk_factors: string[];
  critical_missing_info: string[];
  follow_up_questions: string[];
  suggested_risk_level: RiskLevel;
  short_reason: string;
  llm_used: boolean;
  debug_trace?: DebugTrace | null;
}

export interface DebugTrace {
  gemini_enabled: boolean;
  gemini_used: boolean;
  gemini_model: string;
  gemini_used_for: string[];
  fallback_used: boolean;
  detected_task_intent?: TaskIntent | null;
  detected_task_category?: string | null;
  llm_suggested_risk_level?: RiskLevel | null;
  rule_engine_risk_level?: RiskLevel | null;
  final_risk_level?: RiskLevel | null;
  rules_triggered: string[];
  follow_up_questions: string[];
  critical_missing_info: string[];
  selected_interpretation: string;
  notes: string[];
  gemini_error?: string | null;
  parsed_llm_response?: Record<string, unknown> | null;
  llm_response_text?: string | null;
  llm_prompt?: string | null;
}
