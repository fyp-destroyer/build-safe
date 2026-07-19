// Client-only auth token/user storage. No cookie/session infra exists on
// the backend (JWT bearer only — see core/security.py), so localStorage is
// the simplest approach consistent with lib/api.ts's thin-fetch-wrapper
// convention. Every helper here is a no-op-safe on the server (Next.js can
// render these modules during SSR where `window` doesn't exist).

import type { UserOut } from "./types";

const TOKEN_KEY = "buildsafe-auth-token";
const USER_KEY = "buildsafe-auth-user";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

export function getStoredUser(): UserOut | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as UserOut;
  } catch {
    return null;
  }
}

export function setStoredUser(user: UserOut): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}
