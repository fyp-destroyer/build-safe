# PRD — BuildSafe AI

## 1. What We're Building

BuildSafe AI is a web platform that helps non-expert users decide **whether** a DIY or small construction task is safe to attempt — not just how to do it. A user describes a task in plain language; the system asks follow-up questions, classifies the task into one of five risk levels, explains the decision, recommends tools/materials/PPE with cost and time estimates, and — if the task is too risky — recommends hiring a licensed professional (the product gives guidance, not a quote-routing or booking service).

**One-line pitch:** Existing DIY assistants help users perform tasks. BuildSafe AI helps users decide whether they should perform the task at all.

## 2. Target Users

| User | What they need |
|---|---|
| Homeowner / Tenant | Know if a repair is safe to DIY before spending time/money |
| DIY Beginner | Know what tools/PPE a task needs, and what they don't know they don't know |
| Small Property Owner | Budget/plan before hiring a professional |
| Hardware Vendor | Visibility for tools/materials against relevant tasks |

## 3. Core Features (MVP)

Ranked by priority. Build top-down; cut from the bottom under time pressure.

1. **Conversational task intake** — the user describes the task in a chat interface; description, category, location, skill level, budget, urgency, optional photos are captured through the conversation rather than a multi-field form.
2. **Follow-up questions** — dynamically generated, asked as chat messages, to close safety-critical information gaps (e.g., "is the power isolated?").
3. **Risk classification** — hybrid engine assigns one of five levels: `Safe DIY → DIY with Supervision → Professional Recommended → Professional Required → Dangerous / Do Not Attempt`. The rubric (risk levels, escalation logic) is hardcoded; an LLM classifies which hardcoded hazard rules apply to the described task (see `rules.md` §4 and `architecture.md` §1 for the non-negotiable boundary this still respects).
4. **Risk explanation** — every classification ships with the specific factors/rules that drove it, rendered as a rich card inline in the chat. No black-box output.
5. **Tool & material recommendation** — required vs. optional tools, materials, PPE, with cost range, time range, difficulty — shown inline in the risk assessment card.
6. **User dashboard** — assessment history, saved recommendations.

## 4. Explicitly Out of Scope (MVP)

- Payment processing or contractor escrow
- Legally certified permit verification for any city/jurisdiction
- Computer-vision structural diagnosis from photos
- Real-time contractor location tracking
- Any guarantee of professional work quality or legal compliance
- Admin dashboard / runtime-editable safety rules — the rule set is hardcoded and LLM-assisted at authoring time, changed via code review and redeploy, not a live admin UI (see `rules.md` §4 and `architecture.md` §1)
- Professionals as app users at all — no professional accounts, dashboard, leads, or quote-routing/marketplace. The product's job ends at recommending the user hire a professional; connecting with one happens outside the app.

## 5. Success Criteria

- High **recall on high-risk classes** (Professional Required / Dangerous) — this matters more than raw accuracy. A missed danger is worse than an over-cautious warning.
- Every assessment has a **traceable explanation** (rule or feature-based, not free-text invention).
- End-to-end demo works for all five risk levels: Safe DIY → Dangerous/Do Not Attempt.
- The chat interface feels as fluid and familiar as ChatGPT/Gemini/Claude — no clunky multi-page forms for the core task-intake flow.

## 6. Key Product Principle

**The rule engine is the safety net, the ML model is the first pass.**
`final_risk = max(ML-predicted risk, rule-engine risk)`
The rule engine can only push risk *up*, never down. If in doubt, escalate — never assume safety.

## 7. Open Questions (resolve before/while building)

- Minimum acceptable dataset size and expert-review process for the classifier.
- Acceptable false-negative rate (high-risk task misclassified as low-risk) for launch/demo.
