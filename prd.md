# PRD — CanIDIY

## 1. What We're Building

CanIDIY is a web platform that helps non-expert users decide **whether** a DIY or small construction task is safe to attempt — not just how to do it. A user describes a task in plain language; the system asks follow-up questions, classifies the task into one of five risk levels, explains the decision, recommends tools/materials/PPE with cost and time estimates, and — if the task is too risky — recommends hiring a licensed professional (the product gives guidance, not a quote-routing or booking service).

**One-line pitch:** Existing DIY assistants help users perform tasks. CanIDIY helps users decide whether they should perform the task at all.

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

Both items below were originally scoped to require supervisor sign-off. With no supervisor available, they were resolved provisionally on 2026-07-19 so Phase 1 could proceed — see `phases.md` Phase 1 and `memory.md` for the decision log. Treat these as the working targets for Phases 2-4; revisit with the supervisor when available and update this section if they give a different answer.

- **Minimum dataset size and expert-review process.** *Provisional (pending supervisor confirmation):* target ~150–300 labeled examples per risk class (~1,000–1,500 total) for the Phase 3 TF-IDF+Logistic Regression baseline, scaling up in Phase 4 if time allows — a defensible size for an FYP-scale 5-class text classifier, not a supervisor-set figure. In place of a live domain-expert review (none available), every labeled example and every hardcoded safety rule is instead cross-checked against written authoritative standards — OSHA's Focus Four (already cited in `srs.md` §1.4), local building/electrical codes, and manufacturer/PPE safety sheets — with the source documented inline in `rules.md`/`ai/rule_engine/` so a real expert can audit it in one pass later.
- **Acceptable false-negative rate.** *Provisional (pending supervisor confirmation):* target **≥95% recall** on the two most severe classes (Professional Required, Dangerous/Do-Not-Attempt), measured in the Phase 3/4 eval report — consistent with §5's stated principle that a missed danger is worse than an over-cautious warning. Exact tolerance may be tightened once real evaluation data exists.
