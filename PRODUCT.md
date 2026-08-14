# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: **homeowners, tenants, and DIY beginners** standing in front of a job
they have not done before — a dead socket, a leaking trap, a wall they want to
open up. The deciding moment happens before any work starts, usually with a
phone in hand, often mid-problem rather than at a planning desk. Their job is
not "learn how to do this." It is: *should I be doing this at all, or am I about
to hurt myself or make it worse?*

Secondary, confirmed in `prd.md` §2 but not the page audience: small property
owners budgeting before hiring, and hardware vendors wanting visibility for
tools against relevant tasks.

Explicitly **not** users: tradespeople. There are no professional accounts,
leads, quote-routing, or marketplace — by design (`prd.md` §4).

## Product Purpose

CanIDIY decides *whether* a DIY or small-construction task is safe for this
person to attempt, and says so plainly. The user describes the task in plain
language; the system asks the follow-up questions that close safety-critical
gaps, classifies the task into one of five risk levels, shows the specific
rules that drove the decision, and recommends the tools, materials and PPE the
job actually needs — or tells them to hire a licensed professional.

Success is **recall on the dangerous classes**, not raw accuracy. A missed
danger is worse than an over-cautious warning (`prd.md` §5).

## Positioning

Every other DIY assistant answers *how*. This one answers *whether* — and it is
built so that it structurally cannot be talked out of a safety call.

The mechanism a neighboring product could not truthfully copy:
`finalRisk = max(ML classifier output, rule engine output)`. A hardcoded rule
engine sits underneath a trained classifier and **can only escalate risk, never
lower it**. The LLM in the system is never allowed to pick a risk number — it
phrases follow-up questions, tags which hardcoded hazard rules match the text,
and turns triggered rules into explanation copy. Nothing else. The rule set is
not admin-editable and not runtime-editable; changing it takes a code review and
a redeploy.

Two consequences that are product facts, not implementation detail:

- A missing or "unsure" answer to a safety-critical follow-up **escalates** risk
  (treated as the worst plausible case). It never assumes safety.
- If the AI pipeline fails, the assessment is marked failed and the DIY
  recommendation is blocked. There is no silent fallback to a "safe" result.

## Operating Context

Task intake is **conversational, not a form** — the user types the job the way
they would describe it to a friend, and the follow-ups arrive as chat messages.
The interface is deliberately as familiar as ChatGPT/Gemini/Claude in structure
(sidebar, thread, bottom composer) because the intake has to feel frictionless
mid-problem.

Assessment history is grouped by trade category (Electrical, Plumbing,
Carpentry, Masonry, Painting, Tiling, HVAC, Roofing, General), not by recency,
and past assessments are exportable as JSON.

## Capabilities and Constraints

Confirmed and shipped:

- Conversational task intake with dynamically generated follow-up questions.
- Five risk levels, locked in this order: Safe DIY → DIY with Supervision →
  Professional Recommended → Professional Required → Dangerous / Do Not Attempt.
- Per-assessment explanation listing the specific factors and rules that fired.
- Required vs. optional tools, materials and PPE, with cost range, time range
  and difficulty.
- Assessment history and dashboard, single `user` role, ownership-scoped.

Not built, and must never be implied on any surface (`prd.md` §4):

- No payments, escrow, contractor booking, quote routing, or professional
  accounts of any kind.
- No legally certified permit verification.
- No computer-vision diagnosis from photos.
- No guarantee of professional work quality or legal compliance.
- No admin dashboard or runtime-editable rules.
- Photo upload and semantic retrieval were specified originally but **not
  implemented** (`srs.md` §10).

Technical: Next.js 16 App Router + Tailwind v4 on Vercel, Convex for database
and all backend functions, Clerk for auth via headless hooks. The classifier is
a scikit-learn TF-IDF + Logistic Regression model trained offline and evaluated
in TypeScript at runtime.

## Brand Commitments

- Name: **CanIDIY** (renamed from "BuildSafe AI" on 2026-08-12).
- The visual world is already established and documented in `design.md`:
  safety-orange (`#C2410C` light / `#F97316` dark) against near-black
  (`#060606`), Inter throughout, one hand-rolled stroke icon set, and
  inspection-log framing rather than messaging-app framing.
- The **five risk colors are a locked functional system** — green, blue, amber,
  orange, red — carrying real safety meaning. They must never be reused
  decoratively, and brand orange must never be used to imply a risk level.
  Risk color is always paired with a label and an icon, never color alone.
- No marketing gradients (`design.md` §1).
- Voice: plain, direct, unhedged. It tells someone not to do something.

## Evidence on Hand

- Real, verifiable product mechanism: the rule engine, its catalog, and the
  `max(ML, rules)` composition — all in `apps/frontend/convex/ai/`.
- Real test surface: 2,895 rule-engine evaluations replayed against a reviewed
  baseline (`npm run verify:rules`), plus a dead-parameter guard asserting every
  follow-up's escalation floor can actually change an outcome.
- Classifier verified identical to scikit-learn's own predictions to 1.55e-15.

**Absent and not to be fabricated:** no users, no testimonials, no press, no
customer logos, no adoption numbers, no third-party certification, no published
accuracy figure cleared for marketing use. The ≥95% recall target in `prd.md`
§7 is a *provisional target pending supervisor confirmation*, not a measured
result, and must not be presented as one.

Sample assessments shown on marketing surfaces are **synthetic and must be
labeled as illustrative** (user-confirmed, 2026-08-12).

## Product Principles

1. **Escalate under uncertainty.** Unknown, unsure, or missing always resolves
   toward the more cautious answer. This is the product, not a safeguard on it.
2. **Never a black box.** Every risk level ships with the specific rules that
   produced it. A verdict the user cannot inspect is not shippable.
3. **The decision is the deliverable.** Not instructions, not a contractor
   match, not a quote. The product's job ends at "yes, with these tools" or "no,
   call a professional."
4. **Fail loud.** A broken pipeline shows as failed. It never degrades into a
   reassuring answer.
5. **Familiar to enter, serious to read.** Intake should feel as easy as any
   chat app; the verdict should read like an inspection report.

## Accessibility & Inclusion

- Risk level is never communicated by color alone — always color plus icon plus
  written label (`design.md` §4.2).
- Minimum 4.5:1 contrast on risk chips, already encoded per level.
- Users are non-experts under stress, often on a phone, sometimes one-handed.
  Plain language over jargon is a requirement, not a preference.
