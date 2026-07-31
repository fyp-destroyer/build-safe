// Thin fetch wrapper — NOT axios. Prefixes NEXT_PUBLIC_API_URL, sets JSON headers,
// attaches the stored JWT (if any), and throws a typed ApiError on non-2xx
// responses, parsing the backend's `{ "error": { "code", "message", "fields"?
// } }` shape (see rules.md / architecture.md §5).

import { clearToken, getToken, setToken } from "./auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export interface ApiErrorField {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
  [key: string]: unknown;
}

export interface ApiErrorShape {
  error: {
    code: string;
    message: string;
    fields?: ApiErrorField[];
  };
}

export class ApiError extends Error {
  code: string;
  status: number;
  fields?: ApiErrorField[];

  constructor(status: number, code: string, message: string, fields?: ApiErrorField[]) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

export async function apiFetch<T = unknown>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const token = getToken();

  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });

  // The backend hands back a renewed token once the current one is past
  // halfway through its life (core/security.py `_maybe_renew`). Storing it
  // here — at the one place every authenticated request passes through — is
  // what keeps an active user signed in indefinitely instead of being
  // dropped mid-session.
  const renewed = res.headers.get("X-Refreshed-Token");
  if (renewed) setToken(renewed);

  // An expired or invalid token used to leave the app looking signed in —
  // the auth gate only checks that a token EXISTS, and the user's name comes
  // from localStorage — while every request failed with "Invalid or missing
  // authentication credentials" and the sidebar showed "No saved
  // conversations". Observed live: a dead session that looks like data loss.
  // Treat 401 as "session over": clear the token and send them to log in.
  //
  // /auth/* is excluded because a wrong password there is a 401 the login
  // form must show inline — redirecting would loop the page on itself.
  if (res.status === 401 && !path.startsWith("/auth/")) {
    clearToken();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.assign("/login");
    }
  }

  if (!res.ok) {
    let code = "UNKNOWN_ERROR";
    let message = `Request to ${path} failed with status ${res.status}`;
    let fields: ApiErrorField[] | undefined;

    try {
      const body = (await res.json()) as ApiErrorShape;
      if (body?.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
        fields = body.error.fields;
      }
    } catch {
      // Response body wasn't valid JSON in the expected error shape — fall
      // back to the generic message above rather than failing silently.
    }

    throw new ApiError(res.status, code, message, fields);
  }

  // Handle empty responses (e.g. 204 No Content) gracefully.
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}
