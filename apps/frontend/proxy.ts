/**
 * Route protection — genuinely enforced before the page renders.
 *
 * Named `proxy.ts`, not `middleware.ts`: Next.js 16 deprecated the `middleware`
 * file convention and renamed it to `proxy` (see
 * node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/proxy.md).
 *
 * This file could not exist under the old auth. The JWT lived in localStorage,
 * which nothing at the edge can read, so /chat was guarded only by a `useEffect`
 * that ran after the page had already been sent and hydrated. The redirect
 * worked, but the protected page shipped to the browser first and flashed before
 * bouncing. That was documented as a deliberate compromise, not an oversight —
 * and removing it is the single biggest structural win from moving to Clerk,
 * whose session lives in a cookie the edge can actually see.
 *
 * WHY NOT `createRouteMatcher`
 * ---------------------------
 * Clerk deprecated it, and its reasoning is worth taking seriously: path
 * matching here can diverge from how Next.js actually routes a request, so a
 * matcher that looks right can still leave a resource reachable. Their guidance
 * is to authorise where the data is read.
 *
 * This app already does exactly that, and always did — every Convex query,
 * mutation and action begins with `requireUser` and scopes by owner, returning
 * "not found" rather than "forbidden" for another user's row. No data is
 * reachable without a valid session regardless of what happens at this layer.
 *
 * So this file is deliberately NOT the security boundary. It is a redirect for
 * humans: it sends a signed-out visitor to the sign-in screen instead of letting
 * them stare at an empty chat whose queries are all failing. Keeping it that
 * narrow is why a plain prefix check is sufficient, and why a matcher bug here
 * could cost a nicer error page but never data.
 */

import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

/** Routes that are useless without a session, so a redirect beats a blank page. */
const PROTECTED_PREFIXES = ["/chat", "/dashboard"];

export default clerkMiddleware(async (auth, req) => {
  const { pathname } = req.nextUrl;
  const isProtected = PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
  if (!isProtected) return;

  const { userId } = await auth();
  if (userId) return;

  // Redirect to this app's OWN sign-in screen, preserving where they were
  // headed. Clerk's hosted page would work but would replace the custom design.
  const signIn = new URL("/login", req.url);
  signIn.searchParams.set("redirect_url", req.url);
  return NextResponse.redirect(signIn);
});

export const config = {
  matcher: [
    // Everything except Next internals and static files, unless they appear in
    // a search param.
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    // Always run for API routes.
    "/(api|trpc)(.*)",
  ],
};
