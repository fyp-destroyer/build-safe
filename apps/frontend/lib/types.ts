// Frontend mirror of the FastAPI backend's Pydantic wire contract — see
// apps/backend/schemas/{auth,job,assessment,recommendation}.py. These are
// the *transport* shapes returned by lib/api.ts calls; UI-facing shapes
// (RiskCardData, ChatMessage, HistoryItem) live in lib/chatData.ts and are
// built FROM these by app/chat/page.tsx, not used directly by components.

// ---- auth.py ----

export type BackendTaskCategory =
  | "electrical"
  | "plumbing"
  | "carpentry"
  | "masonry"
  | "painting"
  | "tiling"
  | "hvac"
  | "roofing"
  | "general";

export interface UserOut {
  id: string;
  email: string;
  name: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserOut;
}

// ---- job.py ----

export type JobStatus = "pending_followup" | "ready_to_assess" | "assessed" | "failed";

export interface FollowupPrompt {
  field: string;
  question: string;
}

export interface JobOut {
  id: string;
  user_id: string;
  description: string;
  category: string;
  skill_level: string;
  urgency: string;
  followup_answers: Record<string, boolean>;
  status: JobStatus;
  created_at: string;
  next_followup: FollowupPrompt | null;
}

export interface AssessJobResponse {
  job_id: string;
  status: "completed" | "failed";
  risk_level: number | null;
}

// ---- assessment.py ----

export interface RiskAssessmentOut {
  id: string;
  job_id: string;
  risk_level: number; // 1-5
  confidence: number;
  explanation: string;
  hazard_tags: string[];
  triggered_rules: string[];
  /** Plain-language guidance per triggered rule, from the backend's
   *  hardcoded rule catalog. Preferred over prettifying raw rule slugs. */
  safety_notes?: string[];
  cost: string | null;
  time: string | null;
  difficulty: string | null;
  status: "completed" | "failed";
  created_at: string;
}

// ---- recommendation.py ----

export interface RecommendedItem {
  name: string;
  category: string;
  required: boolean;
  note: string;
}

export interface RecommendationsOut {
  job_id: string;
  risk_level: number;
  items: RecommendedItem[];
  is_placeholder: boolean;
}
