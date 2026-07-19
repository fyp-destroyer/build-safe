import { apiFetch, ApiError } from "@/lib/api";

// Phase 0 health-check page: server-fetches the backend's GET /health.
// The backend isn't guaranteed to be running yet — force-dynamic keeps this
// off the static build path so a failed fetch shows an error state at
// request time instead of breaking `next build`.
export const dynamic = "force-dynamic";

interface HealthResponse {
  status: string;
  [key: string]: unknown;
}

async function getHealth(): Promise<
  { ok: true; data: HealthResponse } | { ok: false; message: string }
> {
  try {
    const data = await apiFetch<HealthResponse>("/health");
    return { ok: true, data };
  } catch (err) {
    const message =
      err instanceof ApiError
        ? `${err.code}: ${err.message}`
        : err instanceof Error
          ? err.message
          : "Unknown error contacting backend";
    return { ok: false, message };
  }
}

export default async function Home() {
  const result = await getHealth();

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-zinc-50 p-8 font-sans dark:bg-black">
      <h1 className="text-2xl font-semibold text-black dark:text-zinc-50">
        BuildSafe AI — Frontend Scaffold
      </h1>

      {result.ok ? (
        <p className="rounded-md bg-green-100 px-4 py-2 text-green-800 dark:bg-green-900/40 dark:text-green-300">
          Backend: ok ({JSON.stringify(result.data)})
        </p>
      ) : (
        <p className="rounded-md bg-red-100 px-4 py-2 text-red-800 dark:bg-red-900/40 dark:text-red-300">
          Backend: unreachable — {result.message}
        </p>
      )}

      <p className="max-w-md text-center text-sm text-zinc-500 dark:text-zinc-400">
        Phase 0 scaffold. See docs/phases.md and docs/architecture.md for what
        comes next.
      </p>
    </div>
  );
}
