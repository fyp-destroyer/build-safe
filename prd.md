# PRD — CanIDIY

## 1. What We're Building

CanIDIY is a web platform that helps non-expert users decide **whether** a DIY or small construction task is safe to attempt, before helping them with anything else. A user describes a task in plain language (optionally attaching photos, in English or Urdu); the system asks follow-up questions, classifies the task into one of five risk levels, and explains the decision.

**The risk level then gates what the product offers next.** This is the product's core mechanic, not a presentation detail:

| Risk level | What the user gets |
|---|---|
| Safe DIY (and provisionally DIY with Supervision, see §7) | Tools/materials/PPE recommendations, plus step-by-step guidance for the task |
| Professional Recommended, Professional Required | Recommendation to hire a professional, plus discovery of relevant trades nearby. No how-to guidance. |
| Dangerous / Do Not Attempt | No guidance of any kind. Professional or emergency referral in its strongest form, plus the immediate safety action (e.g. evacuate, do not operate switches). The system says stop, why, and who to call. |

Note the last row: "do not attempt" restricts what the *user* should do, not what the
product should tell them. A dangerous task needs a professional more urgently than a
merely risky one, so referral gets stronger as risk rises, while guidance stops entirely.

**One-line pitch:** Existing DIY assistants help users perform tasks. CanIDIY decides whether the user should perform the task at all, and only helps them perform it once the answer is yes.

## 2. Target Users

| User | What they need |
|---|---|
| Homeowner / Tenant | Know if a repair is safe to DIY before spending time/money |
| DIY Beginner | Know what tools/PPE a task needs, and what they don't know they don't know |
| Small Property Owner | Budget/plan before hiring a professional |
| Hardware Vendor | Visibility for tools/materials against relevant tasks |
| Urdu-first user | Describe a task in the language they think in, without losing safety accuracy |

## 3. Core Features (MVP)

Ranked by priority. Build top-down; cut from the bottom under time pressure.

1. **Conversational task intake** — the user describes the task in a chat interface; description, category, location, skill level, budget, urgency, optional photos are captured through the conversation rather than a multi-field form.
2. **Follow-up questions** — dynamically generated, asked as chat messages, to close safety-critical information gaps (e.g., "is the power isolated?").
3. **Risk classification** — hybrid engine assigns one of five levels: `Safe DIY → DIY with Supervision → Professional Recommended → Professional Required → Dangerous / Do Not Attempt`. The rubric (risk levels, escalation logic) is hardcoded; an LLM classifies which hardcoded hazard rules apply to the described task (see `rules.md` §4 and `architecture.md` §1 for the non-negotiable boundary this still respects).
4. **Risk explanation** — every classification ships with the specific factors/rules that drove it, rendered as a rich card inline in the chat. No black-box output.
5. **Tool & material recommendation** — required vs. optional tools, materials, PPE, with cost range, time range, difficulty — shown inline in the risk assessment card.
6. **User dashboard** — assessment history, saved recommendations.

Features 1-6 are built. The capabilities below extend them.

## 3a. Planned Capabilities

Ranked by priority, same rule: build top-down, cut from the bottom under time
pressure. Each entry states the constraint that keeps it on the safe side of the
`rules.md` §4 boundary. **None of these may influence the risk level.**

7. **Photo attachment and image-assisted hazard identification** — users attach
   photos of the task area at intake. Images feed the same job task text already
   does: identifying **which hardcoded hazard rules apply**. An image can never
   assign a risk level, and an ambiguous image is treated as the hazard being
   *present*, matching how absent follow-up answers already escalate. Structural
   diagnosis by computer vision stays out of scope (§4).
8. **Retrieval-augmented tool & material recommendation** — retrieval over a
   curated catalog of tools, materials, and PPE, so recommendations are specific
   and traceable to a catalog entry rather than freely generated, including
   substitutes when an item is unavailable. Reuses the existing pgvector
   storage. Advises on equipment only; no influence on risk.
9. **Step-by-step guidance for low-risk tasks** — structured walkthroughs,
   generated only *after* classification and only for the two lowest risk
   levels. Withheld entirely at Professional Recommended and above. The gate is
   the feature: see §6.
10. **Professional discovery via mapping/places service** — for tasks at
    Professional Recommended and above, surface relevant trades nearby, with the
    referral getting *stronger* as risk rises rather than dropping away at the
    top (§1). Directory lookup only: no professional accounts, no quote routing,
    no payments, no endorsement (§4). At Dangerous, the immediate safety action
    comes first and the referral second; neither is replaced by the other.
11. **Urdu and multilingual support** — interface and task intake in Urdu
    alongside English. Hazard rule matching and safety explanation wording must
    be validated **separately per language**; a mistranslated safety warning is a
    safety defect, not a cosmetic one. See §7 for the unresolved model decision.

## 4. Explicitly Out of Scope

- Payment processing or contractor escrow
- Legally certified permit verification for any city/jurisdiction
- Computer-vision structural diagnosis from photos. Photos are in scope (§3a.7)
  but only to help identify which *existing* hazard rules apply. The product
  never diagnoses structural condition, never estimates load or integrity, and
  never derives a risk level from an image.
- Real-time contractor location tracking
- Any guarantee of professional work quality or legal compliance
- Admin dashboard / runtime-editable safety rules — the rule set is hardcoded and LLM-assisted at authoring time, changed via code review and redeploy, not a live admin UI (see `rules.md` §4 and `architecture.md` §1)
- Professionals as app users at all: no professional accounts, dashboards,
  leads, quote-routing, bidding, messaging, or marketplace. §3a.10 adds
  *discovery* of nearby trades through a third-party mapping/places service,
  which is a read-only directory lookup over public data. The distinction is
  load bearing: the product surfaces who exists, it does not broker, rank by
  commercial relationship, vouch for, or transact with anyone. Listings carry no
  claim about competence, licensing, or insurance, and this must be stated in the
  UI rather than only here.
- Any how-to guidance for tasks at Professional Recommended or above. Guidance
  exists only below that line (§3a.9). "The user asked nicely" is not an
  unlock condition.

## 5. Success Criteria

- High **recall on high-risk classes** (Professional Required / Dangerous) — this matters more than raw accuracy. A missed danger is worse than an over-cautious warning.
- Every assessment has a **traceable explanation** (rule or feature-based, not free-text invention).
- End-to-end demo works for all five risk levels: Safe DIY → Dangerous/Do Not Attempt.
- The chat interface feels as fluid and familiar as ChatGPT/Gemini/Claude — no clunky multi-page forms for the core task-intake flow.
- **Guidance never appears above the line.** No task classified Professional
  Recommended or above ever renders step-by-step instructions. This is a test
  case, not an aspiration, and it belongs in the same suite as the rule engine's
  property tests.
- **Urdu parity on safety, not just on strings.** The two most severe classes
  hold their recall when the same held-out tasks are submitted in Urdu. A
  localisation that translates the UI but degrades hazard matching is a failed
  localisation.

## 6. Key Product Principle

**The rule engine is the safety net, the ML model is the first pass.**
`final_risk = max(ML-predicted risk, rule-engine risk)`
The rule engine can only push risk *up*, never down. If in doubt, escalate — never assume safety.

**The risk decision is the gate, not a label.**
Everything the product offers after classification is a function of the risk
level: guidance below the line, professional discovery above it, neither at the
top. Adding step-by-step guidance (§3a.9) does not weaken §1's "whether, not
how" position, it operationalises it. The product still refuses to tell anyone
how to do something it has judged unsafe for them; it now simply has something
useful to say when the answer is that the task *is* safe.

The practical consequence is that a misclassification costs more than it used
to. A task wrongly called safe now receives instructions, not just an optimistic
label. That raises the value of the rule engine's escalate-only bias rather than
lowering it, and it is why §3a.9 is gated in code rather than by prompt.

## 7. Open Questions (resolve before/while building)

Both items below were originally scoped to require supervisor sign-off. With no supervisor available, they were resolved provisionally on 2026-07-19 so Phase 1 could proceed — see `phases.md` Phase 1 and `memory.md` for the decision log. Treat these as the working targets for Phases 2-4; revisit with the supervisor when available and update this section if they give a different answer.

- **Minimum dataset size and expert-review process.** *Provisional (pending supervisor confirmation):* target ~150–300 labeled examples per risk class (~1,000–1,500 total) for the Phase 3 TF-IDF+Logistic Regression baseline, scaling up in Phase 4 if time allows — a defensible size for an FYP-scale 5-class text classifier, not a supervisor-set figure. In place of a live domain-expert review (none available), every labeled example and every hardcoded safety rule is instead cross-checked against written authoritative standards — OSHA's Focus Four (already cited in `srs.md` §1.4), local building/electrical codes, and manufacturer/PPE safety sheets — with the source documented inline in `rules.md`/`ai/rule_engine/` so a real expert can audit it in one pass later.
- **Acceptable false-negative rate.** *Provisional (pending supervisor confirmation):* target **≥95% recall** on the two most severe classes (Professional Required, Dangerous/Do-Not-Attempt), measured in the Phase 3/4 eval report — consistent with §5's stated principle that a missed danger is worse than an over-cautious warning. Exact tolerance may be tightened once real evaluation data exists.
- **How Urdu reaches the classifier (unresolved, decide early).** Two options,
  and they are not equivalent on safety. (a) Translate Urdu to English before
  classification: keeps the current model, but puts a translation step *inside*
  the safety path, where a mistranslation becomes a misclassification. (b) Move
  to a multilingual embedding model: handles both languages natively, but
  requires re-validating the classifier and re-running the full eval suite, and
  the larger model worsens the hosting memory constraint. **(b) is the current
  preference** on the grounds that it keeps the number of failure points down,
  but it is not yet committed. This decision blocks §3a.11 and should be settled
  before localisation work starts.
- **Whether the low-risk guidance line sits at level 1 or levels 1-2.** §3a.9
  currently says the two lowest levels. Whether "DIY with Supervision" should
  receive full walkthroughs, abbreviated ones, or none is unresolved. The
  conservative reading is that supervision implies a human present who does not
  need the app's instructions.
