"use client";

/**
 * Creates the caller's Convex `users` row once they are signed in.
 *
 * WHY THIS EXISTS
 * ---------------
 * Clerk owns the account; Convex owns everything the account *has* (jobs,
 * transcripts, assessments). A `users` row is what links the two, and it is the
 * foreign key every other table points at.
 *
 * `users.getOrCreateCurrent` was written to create that row just-in-time — but
 * nothing called it. So signing in produced a user in Clerk and no user in
 * Convex, and the row only appeared later as a side effect of creating a first
 * job. Until then every query was scoped to a user that did not exist.
 *
 * A query cannot fix this itself: Convex queries cannot write. It has to be a
 * mutation, fired from the client once the session exists — which is exactly
 * what this component is.
 *
 * It renders nothing and sits in the provider tree, so any signed-in page gets
 * the row without having to remember to ask for it.
 */

import { useEffect, useRef } from "react";
import { useConvexAuth, useMutation } from "convex/react";
import { api } from "@/convex/_generated/api";

export function EnsureConvexUser() {
  const { isAuthenticated, isLoading } = useConvexAuth();
  const getOrCreate = useMutation(api.users.getOrCreateCurrent);
  const done = useRef(false);

  useEffect(() => {
    // `useConvexAuth`, not Clerk's `useUser`: this must wait until Convex itself
    // has accepted the token. Clerk can report a signed-in user a moment before
    // Convex has verified the JWT, and calling then just throws "Not
    // authenticated".
    if (isLoading || !isAuthenticated || done.current) return;
    done.current = true;

    void getOrCreate({}).catch((err) => {
      // Non-fatal by design. The row is also created on demand by the job-creation
      // action, so a failure here costs a retry, not the session. Logged rather
      // than surfaced because there is nothing the user could do about it.
      done.current = false;
      console.error("EnsureConvexUser: failed to create user record", err);
    });
  }, [isAuthenticated, isLoading, getOrCreate]);

  return null;
}
