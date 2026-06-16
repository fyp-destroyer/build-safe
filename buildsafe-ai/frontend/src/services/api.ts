import type { AssessmentRequest, AssessmentResponse, SeedDataResponse } from "../types/assessment";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

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
