/**
 * Clerk as Convex's auth provider.
 *
 * `CLERK_JWT_ISSUER_DOMAIN` is set in the Convex dashboard (Settings →
 * Environment Variables), separately per deployment — it is read by the Convex
 * backend at runtime, not by Next.js, so it does not belong in .env.local's
 * NEXT_PUBLIC_ space.
 *
 * `applicationID: "convex"` must match the name of the JWT template created in
 * the Clerk dashboard. Clerk's Convex template is named `convex` by default;
 * renaming it there without changing it here breaks every authenticated call.
 */

export default {
  providers: [
    {
      domain: process.env.CLERK_JWT_ISSUER_DOMAIN!,
      applicationID: "convex",
    },
  ],
};
