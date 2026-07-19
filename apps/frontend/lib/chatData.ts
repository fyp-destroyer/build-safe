import type { RiskLevel } from "./riskLevels";

export type MessageRole = "user" | "assistant";

export interface RiskCardData {
  level: RiskLevel;
  taskTitle: string;
  summary: string;
  factors: string[];
  requiredTools?: string[];
  optionalTools?: string[];
  toolsWithheld?: string;
  cost: string;
  time: string;
  nextStep:
    | { kind: "checklist"; items: string[] }
    | { kind: "consult"; category: string; blurb: string };
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  text?: string;
  quickReplies?: string[];
  riskCard?: RiskCardData;
  createdAt: number;
  // Set on assistant messages that report a failed network/API call (e.g. a
  // thrown ApiError) — rendered as a distinct inline error bubble by
  // app/chat/page.tsx rather than a normal MessageBubble. Never set together
  // with riskCard: a `status: "failed"` *assessment* is a valid 200 response
  // and always renders as a normal (worst-case) RiskCard, not this — see
  // rules.md §4 point 4 / the AI-pipeline-failure handling in job_service.py.
  isError?: boolean;
}

// Locked task category list — sidebar grouping, icon mapping, and any future
// backend taxonomy must all agree on this exact set and order.
export type TaskCategory =
  | "Electrical"
  | "Plumbing"
  | "Carpentry"
  | "Masonry"
  | "Painting"
  | "Tiling"
  | "HVAC"
  | "Roofing"
  | "General";

export const CATEGORY_ORDER: TaskCategory[] = [
  "Electrical",
  "Plumbing",
  "Carpentry",
  "Masonry",
  "Painting",
  "Tiling",
  "HVAC",
  "Roofing",
  "General",
];

export interface HistoryItem {
  id: string;
  title: string;
  category: TaskCategory;
  createdAt: number;
  favourite?: boolean;
}

// Populated at runtime from GET /jobs by app/chat/page.tsx — see that
// file's `jobToHistoryItem`. Ordered by recency (most recent first), not
// grouped by category — the category still rides along on each item (shown
// as a caption under the title) but no longer drives the list's structure.
// Favourited items are pulled into their own section above the rest (a
// client-only, non-persisted toggle — the backend has no concept of it);
// see Sidebar.tsx.
