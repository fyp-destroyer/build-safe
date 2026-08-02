import { redirect } from "next/navigation";

/**
 * Entry point — always the sign-in screen.
 *
 * This used to be the Phase 0 scaffold page: it server-fetched the FastAPI
 * backend's GET /health and rendered "Backend: ok" or "Backend: unreachable".
 * That page existed to prove the frontend could reach the backend at all, and
 * there is no longer a separate backend to reach — Convex is called directly by
 * the components that need it, and its health is not something a user should be
 * shown.
 *
 * It briefly redirected to /chat instead, letting `proxy.ts` bounce signed-out
 * visitors onward to /login. That worked but cost a visible double hop on the
 * deployed site (/ -> /chat -> /login) for the most common case: someone opening
 * the URL for the first time. Going straight to /login makes the front door of
 * the deployment a single, predictable redirect.
 *
 * Note this is unconditional, so an already-signed-in user opening the root also
 * lands on /login rather than being taken to their chat. That is the intended
 * behaviour here; if it should instead skip straight to /chat when a session
 * exists, this becomes a server-side `auth()` check rather than a bare redirect.
 */
export default function Home() {
  redirect("/login");
}
