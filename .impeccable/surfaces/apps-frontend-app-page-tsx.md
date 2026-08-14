---
version: 1
slug: "apps-frontend-app-page-tsx"
primary_target: "apps/frontend/app/page.tsx"
related_targets: ["apps/frontend/components/landing/LandingPage.tsx"]
---

Scope: `/` — the marketing homepage. Visitor mode: Persuade.

Audience: homeowners, tenants and DIY beginners standing in front of a job they have
not done before, usually mid-problem and on a phone. Not tradespeople — there are no
professional accounts in this product.

Job: decide whether to attempt the task at all, and get far enough into trusting the
system to start one assessment. Success is one click into /chat.

Action: a single primary CTA, "Start an assessment", pointing at `/chat` for everyone.
`proxy.ts` bounces signed-out visitors to /login with a redirect_url, so no auth state
is read to render the page and the control works before Clerk loads.

There is deliberately no separate "Sign in" control in the header (removed 2026-08-12 at
the user's direction). Because of that redirect it went to the same screen as the button,
so the two competed for one outcome; returning users press the button. Session state only
changes the button's label ("Start an assessment" → "Open CanIDIY"). The footer keeps its
Sign in / Create account links, where they are navigation rather than a rival CTA.

Proof: three assessments filed in full, each showing the engine overruling itself —
rule ids, floors, follow-up wording and the max(ML, rules) composition are quoted from
the shipped catalog; the task text and reference numbers are authored illustrations and
are labelled as such. No usage counts, testimonials, or accuracy figures appear, and the
provisional ≥95% recall target from prd.md §7 is deliberately absent.

Constraints: inherits the existing token world (design.md) rather than introducing a
second identity. Always-dark via a `dark` class on the page root — it leads directly
into the always-dark auth screen and must not invert halfway. Risk colour only ever
appears as colour + icon + label. Brand orange never implies a risk level.

Direction: the page is the product's own case register — a key, filed entries, the
standing clauses that govern them, and a scope note. Chosen structure was candidate 6
of the grounded list (seed adb6da48). The memorable moment is the verdict stamp landing
on each entry: the page's only entrance animation, with the same verdict also present
as text so nothing load-bearing depends on it.

Unresolved: the close is a plain CTA rather than a working composer, because the
assessment pipeline requires an authenticated Convex user and a fake input would be
dishonest. If an unauthenticated demo path is ever built, the close is where it goes.
