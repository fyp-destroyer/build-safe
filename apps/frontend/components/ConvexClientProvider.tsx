"use client";

/**
 * Wires Clerk's session into Convex.
 *
 * `ConvexProviderWithClerk` takes Clerk's `useAuth` and uses it to fetch a JWT
 * from the Clerk template named `convex`, attaching it to every Convex call.
 * That token is what `ctx.auth.getUserIdentity()` reads on the backend, so this
 * component is the whole of the client-side auth wiring — individual queries
 * never handle a token.
 *
 * Client component because both providers rely on React context and browser
 * state; it wraps the app in the root layout, which stays a server component.
 */

import { ReactNode } from "react";
import { ConvexReactClient } from "convex/react";
import { ConvexProviderWithClerk } from "convex/react-clerk";
import { ClerkProvider, useAuth } from "@clerk/nextjs";
import { EnsureConvexUser } from "./EnsureConvexUser";

const convex = new ConvexReactClient(process.env.NEXT_PUBLIC_CONVEX_URL!);

export function ConvexClientProvider({ children }: { children: ReactNode }) {
  return (
    <ClerkProvider publishableKey={process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY!}>
      <ConvexProviderWithClerk client={convex} useAuth={useAuth}>
        {/* Renders nothing; creates the Convex `users` row once the session is
            live. Sits here rather than in a page so every authenticated route
            gets it without having to remember. */}
        <EnsureConvexUser />
        {children}
      </ConvexProviderWithClerk>
    </ClerkProvider>
  );
}
