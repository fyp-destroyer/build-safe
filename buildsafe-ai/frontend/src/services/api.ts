import type {
  ActionPlanRequest,
  ActionPlanResponse,
  AssessmentRequest,
  AssessmentResponse,
  FollowupPlanRequest,
  FollowupPlanResponse,
  SeedDataResponse,
  UpdateAssessmentRequest,
  UpdateAssessmentResponse,
} from "../types/assessment";
import { API_BASE_URL } from "../config/api";

type HealthCheckResponse = {
  status: string;
  service: string;
};

export async function healthCheck(signal?: AbortSignal): Promise<HealthCheckResponse> {
  const response = await fetch(`${API_BASE_URL}/health`, { signal });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Backend health check failed"));
  }

  return response.json() as Promise<HealthCheckResponse>;
}

export async function assessTask(
  payload: AssessmentRequest,
): Promise<AssessmentResponse> {
  const response = await fetch(`${API_BASE_URL}/api/assess-task`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to assess task"));
  }

  return response.json() as Promise<AssessmentResponse>;
}

export async function generateActionPlan(
  payload: ActionPlanRequest,
): Promise<ActionPlanResponse> {
  const response = await fetch(`${API_BASE_URL}/api/action-plan`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to generate action plan"));
  }

  return response.json() as Promise<ActionPlanResponse>;
}

export async function planFollowups(
  payload: FollowupPlanRequest,
): Promise<FollowupPlanResponse> {
  const response = await fetch(`${API_BASE_URL}/api/llm/plan-followups`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to plan follow-up questions"));
  }

  return response.json() as Promise<FollowupPlanResponse>;
}

export async function updateAssessment(
  payload: UpdateAssessmentRequest,
): Promise<UpdateAssessmentResponse> {
  const response = await fetch(`${API_BASE_URL}/api/update-assessment`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to update assessment"));
  }

  return response.json() as Promise<UpdateAssessmentResponse>;
}

export async function getSeedData(signal?: AbortSignal): Promise<SeedDataResponse> {
  const response = await fetch(`${API_BASE_URL}/api/admin/seed-data`, { signal });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load seed data"));
  }

  return response.json() as Promise<SeedDataResponse>;
}

async function getErrorMessage(response: Response, fallback: string): Promise<string> {
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    const payload = (await response.json()) as { message?: string; detail?: string };
    return payload.message ?? payload.detail ?? fallback;
  }

  const text = await response.text();
  return text || fallback;
}
