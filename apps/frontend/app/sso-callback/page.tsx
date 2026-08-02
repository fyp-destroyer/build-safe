"use client";

/**
 * OAuth landing page.
 *
 * Google redirects here when a session could NOT be created directly and the
 * flow needs another step — chiefly the sign-in <-> sign-up transfer, which is
 * what happens when someone clicks "Sign in with Google" for an account that
 * does not exist yet. A straightforward successful sign-in goes to
 * `redirectUrl` (/chat) and never reaches this page at all.
 *
 * WHY THIS IS HAND-WRITTEN RATHER THAN <HandleSSOCallback />
 * ----------------------------------------------------------
 * Clerk ships `HandleSSOCallback`, and it encodes exactly the branch logic
 * below. It was used first. The problem is that it is opaque when it fails: the
 * callback simply never navigated, leaving a blank page, and nothing in it says
 * which branch it took or why. Diagnosing that from the outside is guesswork.
 *
 * This version walks the same decision tree with a log line at every branch, so
 * a failure names itself in the console instead of presenting as a blank screen.
 * If it ever proves stable and boring, swapping back to Clerk's component is a
 * one-line change — but the logging is worth more than the brevity while the
 * flow is still being trusted.
 */

import { useSignIn, useSignUp, useClerk } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

/**
 * Read a live status off a Clerk signal object, defeating stale narrowing.
 *
 * `signIn` / `signUp` are mutated in place by `create()` and friends, so after
 * an await their status is not what TypeScript inferred from the checks earlier
 * in the function. Widening to `string` here is the point: it keeps the runtime
 * truth and the compile-time view from disagreeing, which otherwise made the
 * success branch provably-dead code that would never have run.
 */
function statusOf(flow: { status?: string | null }): string | null {
  return flow.status ?? null;
}

export default function SSOCallback() {
  const router = useRouter();
  const clerk = useClerk();
  const { signIn } = useSignIn();
  const { signUp } = useSignUp();
  const hasRun = useRef(false);
  const [detail, setDetail] = useState<string | null>(null);

  useEffect(() => {
    if (!clerk.loaded || !signIn || !signUp || hasRun.current) return;
    hasRun.current = true;

    const log = (...args: unknown[]) => console.log("[sso-callback]", ...args);

    /** Clerk may hand back an absolute URL; only push() takes a relative one. */
    const go = (destination: string) => {
      log("navigating to", destination);
      if (destination.startsWith("http")) {
        window.location.href = destination;
        return;
      }
      router.replace(destination);
    };

    (async () => {
      log("state", {
        signInStatus: signIn.status,
        signUpStatus: signUp.status,
        signInTransferable: signIn.isTransferable,
        signUpTransferable: signUp.isTransferable,
        signInExistingSession: Boolean(signIn.existingSession),
        signUpExistingSession: Boolean(signUp.existingSession),
        // The fields that actually matter when a sign-up stalls: `missingFields`
        // names precisely what the Clerk instance demands that Google did not
        // supply, which is the difference between a fixable dashboard setting
        // and an unexplained dead end.
        missingFields: signUp.missingFields,
        unverifiedFields: signUp.unverifiedFields,
        requiredFields: signUp.requiredFields,
      });

      try {
        // 1. Sign-in already finished — just activate the session.
        if (signIn.status === "complete") {
          log("branch: signIn complete -> finalize");
          const { error } = await signIn.finalize({ navigate: async () => go("/chat") });
          if (error) throw error;
          return;
        }

        // 2. Sign-up already finished.
        if (signUp.status === "complete") {
          log("branch: signUp complete -> finalize");
          const { error } = await signUp.finalize({ navigate: async () => go("/chat") });
          if (error) throw error;
          return;
        }

        // 3. THE COMMON CASE. "Sign in with Google" for an account that does not
        //    exist yet: Clerk starts a sign-IN, finds nobody, and marks the
        //    attempt transferable to a sign-UP. Without this the user is
        //    authorised by Google and still refused by the app.
        if (signIn.isTransferable) {
          log("branch: signIn -> signUp transfer");
          const { error } = await signUp.create({ transfer: true });
          if (error) throw error;

          // Re-read through `statusOf`. These are signal objects that `create`
          // MUTATES in place, so the status here is not the one TypeScript
          // narrowed from the checks above — without this, `=== "complete"`
          // is a compile error against a stale narrowing and the success path
          // would have been unreachable.
          if (statusOf(signUp) === "complete") {
            const { error: e2 } = await signUp.finalize({ navigate: async () => go("/chat") });
            if (e2) throw e2;
            return;
          }
          log("transfer did not complete; signUp.status =", statusOf(signUp));
          setDetail(
            `Google signed you in, but the account could not be created ` +
              `automatically (status: ${statusOf(signUp) ?? "unknown"}). This usually ` +
              `means the Clerk instance asks for a field Google did not supply.`,
          );
          return;
        }

        // 4. The reverse: a sign-UP for somebody who already has an account.
        if (signUp.isTransferable) {
          log("branch: signUp -> signIn transfer");
          const { error } = await signIn.create({ transfer: true });
          if (error) throw error;
          if (statusOf(signIn) === "complete") {
            const { error: e2 } = await signIn.finalize({ navigate: async () => go("/chat") });
            if (e2) throw e2;
            return;
          }
          log("reverse transfer did not complete; signIn.status =", statusOf(signIn));
          return go("/login?sso=incomplete");
        }

        // 5. Already signed in on another tab / previous session.
        const existing = signIn.existingSession ?? signUp.existingSession;
        if (existing?.sessionId) {
          log("branch: existing session", existing.sessionId);
          await clerk.setActive({ session: existing.sessionId });
          return go("/chat");
        }

        // 6. Genuinely needs more from the user.
        if (signIn.status === "needs_first_factor" || signIn.status === "needs_second_factor") {
          log("branch: needs another factor");
          return go("/login?sso=needs_factor");
        }

        // 7. The sign-up exists but Clerk wants fields the OAuth provider did
        //    not supply. Almost always a dashboard setting rather than a code
        //    problem: if "Password" is a REQUIRED attribute, no Google sign-up
        //    can ever complete, because Google has no password to hand over.
        if (statusOf(signUp) === "missing_requirements") {
          const missing = signUp.missingFields ?? [];
          log("branch: missing_requirements", { missing, unverified: signUp.unverifiedFields });
          setDetail(
            missing.length > 0
              ? `Google authorised you, but this Clerk instance also requires: ` +
                  `${missing.join(", ")} — which Google does not provide. Make ` +
                  `those fields optional in the Clerk dashboard (Configure → ` +
                  `Email, Phone, Username), then try again.`
              : `Google authorised you, but the sign-up could not be completed ` +
                  `(missing_requirements, with no specific field reported). Check ` +
                  `that Password is set to optional in the Clerk dashboard.`,
          );
          return;
        }

        log("branch: NONE MATCHED");
        setDetail(
          `The sign-in did not complete and no recovery path applied ` +
            `(signIn: ${signIn.status ?? "none"}, signUp: ${signUp.status ?? "none"}).`,
        );
      } catch (err) {
        // Surface it. A silent failure here is what produced the blank page.
        console.error("[sso-callback] failed", err);
        const message =
          err && typeof err === "object" && "message" in err
            ? String((err as { message: unknown }).message)
            : String(err);
        setDetail(message);
      }
    })();
  }, [clerk, clerk.loaded, signIn, signUp, router]);

  // Nothing visible on the happy path — this page is a transition, not a screen.
  // It only renders when something went wrong, because a blank dead end with no
  // explanation is the worst possible outcome of a sign-in attempt.
  if (!detail) return null;

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-[#0a0a0a] px-4 text-white">
      <div className="w-full max-w-sm space-y-4 text-center">
        <h1 className="text-xl font-semibold">Couldn&apos;t finish signing in</h1>
        <p className="text-sm text-white/60">{detail}</p>
        <button
          onClick={() => router.replace("/login")}
          className="w-full cursor-pointer rounded-full bg-[#F97316] py-3 font-medium text-white transition-colors hover:bg-[#EA580C]"
        >
          Back to sign in
        </button>
      </div>
    </div>
  );
}
