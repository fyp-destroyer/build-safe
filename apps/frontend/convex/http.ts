/**
 * HTTP endpoints exposed by Convex.
 *
 * NOTE ON THE URL: HTTP actions are served from the deployment's `.convex.site`
 * domain, NOT the `.convex.cloud` domain used by the client SDK. The webhook
 * endpoint to register in Clerk is:
 *
 *     https://<your-deployment>.convex.site/clerk-webhook
 *
 * Pointing Clerk at `.convex.cloud` is the usual first mistake — it 404s.
 */

import { httpRouter } from "convex/server";
import { httpAction } from "./_generated/server";
import { internal } from "./_generated/api";
import { Webhook } from "svix";

/**
 * Clerk → Convex user sync.
 *
 * WHAT THIS IS AND IS NOT RESPONSIBLE FOR
 * ---------------------------------------
 * It does NOT create users. A `users` row is created just-in-time by
 * `users.getOrCreateCurrent` on the first authenticated call, because
 * `ctx.auth.getUserIdentity()` already carries everything the row needs. Relying
 * on a webhook for creation would open a window where a signed-in user has no
 * row yet — every query would have to handle "authenticated but unknown", and a
 * dropped webhook would strand the account permanently.
 *
 * It exists for the two things JIT creation genuinely cannot cover:
 *
 *   user.updated — the user changed their email or name in Clerk, and our
 *                  denormalised copy would otherwise go stale.
 *   user.deleted — the account is gone, so their jobs, transcripts, assessments
 *                  and AI logs must go with it. Without this, deleting an
 *                  account in Clerk would silently leave all of its data behind,
 *                  which is precisely the data the user asked to be rid of.
 *
 * `user.created` is accepted and treated as an upsert anyway, so that arriving
 * before the user's first request is harmless rather than a duplicate.
 */
const clerkWebhook = httpAction(async (ctx, request) => {
  const secret = process.env.CLERK_WEBHOOK_SECRET;
  if (!secret) {
    // Fail loud. A misconfigured secret must never be mistaken for "no events
    // to process" — that would look healthy while user deletions silently
    // stopped propagating (rules.md §2: never fail silently).
    console.error("clerk-webhook: CLERK_WEBHOOK_SECRET is not set");
    return new Response("Webhook secret not configured", { status: 500 });
  }

  const payload = await request.text();
  const headers = {
    "svix-id": request.headers.get("svix-id") ?? "",
    "svix-timestamp": request.headers.get("svix-timestamp") ?? "",
    "svix-signature": request.headers.get("svix-signature") ?? "",
  };

  // Verify the signature before trusting ANY field in the body. This endpoint
  // is public — without verification, anyone who learned the URL could delete
  // any user's data by POSTing a forged `user.deleted`.
  let event: { type: string; data: Record<string, unknown> };
  try {
    event = new Webhook(secret).verify(payload, headers) as typeof event;
  } catch (err) {
    console.error("clerk-webhook: signature verification failed", err);
    return new Response("Invalid signature", { status: 400 });
  }

  switch (event.type) {
    case "user.created":
    case "user.updated": {
      const data = event.data as {
        id: string;
        email_addresses?: { id: string; email_address: string }[];
        primary_email_address_id?: string | null;
        first_name?: string | null;
        last_name?: string | null;
      };

      // Prefer the primary address; fall back to the first one. A Clerk user
      // can hold several verified addresses.
      const primary =
        data.email_addresses?.find((e) => e.id === data.primary_email_address_id) ??
        data.email_addresses?.[0];

      await ctx.runMutation(internal.users.upsertFromClerk, {
        clerkUserId: data.id,
        email: primary?.email_address ?? "",
        name: [data.first_name, data.last_name].filter(Boolean).join(" ").trim(),
      });
      break;
    }

    case "user.deleted": {
      const data = event.data as { id?: string };
      if (data.id) {
        await ctx.runMutation(internal.users.deleteFromClerk, { clerkUserId: data.id });
      }
      break;
    }

    default:
      // Clerk sends many event types; ignoring the ones we did not subscribe to
      // is correct, but log it so an unexpected subscription is visible.
      console.info(`clerk-webhook: ignoring unhandled event type ${event.type}`);
  }

  return new Response(null, { status: 200 });
});

const http = httpRouter();

http.route({
  path: "/clerk-webhook",
  method: "POST",
  handler: clerkWebhook,
});

export default http;
