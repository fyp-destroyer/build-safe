import type { Metadata } from "next";
import { LandingPage } from "@/components/landing/LandingPage";

/**
 * The front door.
 *
 * This route used to be a bare `redirect("/login")`. That was the right call
 * while there was nothing to show a first-time visitor — the deployment's only
 * surface was the app itself, so the shortest path to it was the best one. It
 * is the wrong call now that the root has something to say: someone arriving
 * cold needs to know what the product decides, on what basis, and what it
 * refuses to do, before being asked for an email address.
 *
 * Nothing here is gated. `proxy.ts` protects /chat and /dashboard only, and its
 * redirect is what lets every call to action on this page point at /chat with a
 * single href: a signed-out visitor is bounced to /login with a redirect_url
 * and lands back in the app after signing in, while a signed-in one goes
 * straight through. No auth state is read to render the page.
 */

export const metadata: Metadata = {
  title: "CanIDIY — should you be doing this yourself?",
  description:
    "Describe a DIY or repair job in plain language. CanIDIY asks the safety questions that change the answer, then files one of five verdicts — with the hardcoded hazard rules that produced it.",
};

export default function Home() {
  return <LandingPage />;
}
