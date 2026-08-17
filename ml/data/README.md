# ml/data — Dataset Creation (Phase 2)

This directory holds the labeled dataset used to train the Phase 3/4 ML risk classifier. See `phases.md` Phase 2 and `srs.md` §12 for the source spec.

## Files

- `seed_examples.json` — **256 hand-written seed examples**, covering all 9 categories and all 5 risk levels. Authoritative and hand-judged; nothing downstream ever relabels these. Each carries a stable `id` (`seed-0001`…) so generated variants can reference their parent.
- `generated_examples.json` — **299 machine-generated variants** (555 total), each carrying `variant_of` (parent seed id) and `generation_rule`. Produced by `../generate_variations.py`; see "Template variation and weak labeling" below.
- `train.json` / `val.json` / `test.json` — the split (387 / 86 / 82 rows = 69.7 / 15.5 / 14.8%). Built by `../make_splits.py`; each row gains `source` (`seed`/`generated`) and `group_id`. See "The split" below.
- `REVIEW.md` — label-quality audit against published safety standards, with its limitations stated plainly. Produced by `../review_high_risk.py`.
- `sources.json` — **the source registry.** Every authority cited by a label, with publisher, jurisdiction, URL and a `verified` date, plus a `rejected` list recording sources that were considered and failed (a withdrawn HSE leaflet, a surveillance system that stopped collecting in 2002, and the most-cited source in an earlier draft, which turned out to be untraceable). Anything with `verified: null` must not be cited — `assign_basis.py` flags it `[UNVERIFIED - do not ship]`.
- `rubric.md` — **how a `risk_level` is arrived at.** `risk_level = max(severity_floor, restriction_floor)`, where both inputs carry citations and the function is published. Read this before changing any label. It also states plainly what may and may not be claimed to a stakeholder — in particular that *no authority publishes a DIY competence scale*, so the 1–5 scale is derived, not borrowed. **If you need to describe this work to a supervisor or in a viva, use the wording in its "What may and may not be claimed" section** — it has both a formal and a plain-English version, and notes the two details that must not be dropped when simplifying further.
- `../assign_basis.py` — writes the `basis` field on every row from the rubric. Writes `basis` **only**; never `risk_level`, `hazards` or `task_text`. Where the rubric disagrees with the hand label it prints a review queue and leaves the label alone. Currently reproduces **192/256 seed labels (75%)**; the remaining disagreements are spread evenly across all nine categories.
- `../validate_dataset.py` — **run `python ml/validate_dataset.py` after every change.** It mechanically enforces every rule documented here (risk/label agreement, the `risk_level: 5` PPE rule, the unanswered-follow-up escalation rule, canonical question wording, enum validity, duplicate detection, and — for generated rows — that each weak-labeling rule did what it claims). Several of these rules exist because a real mistake was caught in review; the validator is what stops them recurring at scale.
- `../generate_variations.py` — regenerates `generated_examples.json` from the seeds. Deterministic: same seeds in, same variants out.

## Template variation and weak labeling

**Template variation** produces surface-form variants of a hand-written seed so the classifier learns the *task* rather than the exact string. **Weak labeling** assigns those variants a label from a rule instead of hand-judging each one.

Weak labeling can quietly produce *wrong safety labels* at scale, and padding to 500 with near-duplicates would pass the exit check while making eval look better than the model is. So the rules here are deliberately constrained — **no rule may ever lower a risk level** (`rules.md` §4.2), and the validator enforces that:

| Rule | n | What it does | Why the label is safe |
|---|---|---|---|
| `WL-1a:rephrase` | 256 | Wraps the task in conversational framing — `"I want to …"`, `"can I … myself?"`, `"… — is that a DIY job?"`, and for problem-report seeds `"… what should I do?"` | Content is unchanged, so the parent label is inherited verbatim. Genuine coverage, not filler: seeds are uniformly bare imperatives, but real chat input is hedged and question-shaped. |
| `WL-1b:room-substitution` | 26 | Swaps one risk-neutral room for another (`bedroom` ↔ `hallway` ↔ `living room` ↔ `dining room` ↔ `spare room`) | Restricted to rooms that carry no safety signal, and skipped entirely where a `water_damage` / `confined_space` / `asbestos_exposure` hazard is present. `bathroom`, `basement`, `loft`, `garage` are never substituted — the room *is* part of the hazard there. `landing` is excluded for reading badly ("an outlet in the landing"). |
| `WL-2:strip-confirmation` | 17 | Removes a stated safety confirmation (`"…, breaker off and verified dead"` → `"…"`), which makes the condition unaddressed → the follow-up returns and `risk_level` becomes 5 | **Escalation only.** Each stripped text is hand-written, not regex-derived, because it changes a safety label. These are the most informative variants in the set: same task, one fact removed, different outcome. |

**Deliberately not automated: de-escalation.** Injecting a confirmation into a seed (which would *lower* risk) is the direction where a wrong label is dangerous, so those variants stay hand-written seeds only.

## The split

`python ml/make_splits.py` (deterministic — no RNG, ordering is by id).

| | rows | % | hand-written | generated |
|---|---|---|---|---|
| train | 387 | 69.7 | 173 | 214 |
| val | 87 | 15.7 | 43 | 44 |
| test | 81 | 14.6 | 40 | 41 |

All five risk levels appear in all three splits, in both the full and hand-written-only views.

**Stratification is on risk level _and_ on problem-report style.** A "problem report" is a task_text describing something already going wrong (`"my gas water heater is hissing"`, `"the roof is sagging"`) rather than an intended action. These are a small, stylistically distinct subpopulation that is almost entirely `risk_level 5`, and they are the highest-stakes inputs the system will ever receive.

Stratifying on risk level alone was not enough: it put 10 of them in train against 14 in test — the test set held *more* of this population than training did — so the model never learned the pattern and mislabelled dangerous emergencies as `safe_diy`. This was found by error analysis on the first Phase 3 baseline run, not by inspection. `make_splits.py` now fails if train holds under 50% of them.

**Grouping is the entire point of this script.** A variant shares almost all its text with its parent, so rows are grouped and assigned to splits atomically: 555 rows → 250 groups. Grouping combines two things:

1. `variant_of` — every generated variant travels with its parent seed.
2. Seed-to-seed relatedness — the deliberate contrast sets (same task, differing only in what the user states) are merged so they cannot straddle a split.

Relatedness needs **both** a sequence-similarity test and a token-containment test. Similarity alone silently misses the most important case: the contrast sets are built by *adding* a clause, and `"install a ceiling fan in my bedroom"` vs the same text plus a long confirmation clause scores only ~0.41 despite one wholly containing the other. Containment catches that shape. With similarity alone the four-example ceiling-fan set was split across train and test.

The script fails rather than writing files if any group spans splits, any class is missing, any split lacks hand-written rows, or any cross-split leak is detected.

**The leak check runs on seed texts only, deliberately.** A generated row cannot leak independently — it is always in its parent's split. Comparing generated text directly also produces false alarms, since every rephrase shares a template wrapper (`"I was going to … from an extension ladder"`), which inflates the similarity of two genuinely different underlying tasks.

**Evaluate on hand-written data.** Rows carry `source`, and hand-written vs generated are kept in separate source files, precisely so the test set can be restricted to seeds. Reporting headline metrics over weakly-labeled rows would measure the generator, not the task.

⚠️ **The hand-written test set is small per class** — 41 rows, roughly 10/7/6/6/12 across risk 1–5. `prd.md` §7's ≥95% recall target applies to the two most severe classes, i.e. **18 test examples**; a single misclassification moves recall by ~5 points. Treat per-class recall as indicative, report confidence intervals rather than bare point estimates, and consider k-fold cross-validation over the grouped data instead of relying on this single split.

**Never commit real user data or PII here** — every record must be synthetic/authored, matching the shape below.

**Note on `urgency`:** the app still collects `urgency` on every job (`apps/backend/schemas/job.py`, required field) purely as a UX/conversational-flow input — it has no bearing on physical safety, so it is deliberately **not** part of the training schema below. (This narrows `srs.md` §8's original wording, which listed urgency as a classifier input; that line has been updated to match.)

## Record schema

```json
{
  "task_text": "install a ceiling fan in my bedroom",
  "category": "electrical",
  "user_skill": "Beginner",
  "tools_available": ["screwdriver", "ladder"],
  "hazards": ["electrical_shock", "fall_from_height"],
  "risk_level": 3,
  "risk_label": "professional_recommended",
  "professional_category": "electrician",
  "suggested_ppe": ["insulated_gloves", "safety_glasses"],
  "followup_questions": [
    {
      "field": "power_isolated",
      "question": "Have you confirmed the power to this circuit is fully isolated at the breaker before starting?",
      "answer": null
    }
  ]
}
```

| Field | Type | Notes |
|---|---|---|
| `task_text` | string | Free-text task description, written the way a real user would phrase it (casual, not textbook) |
| `category` | string | One of the 9 locked categories below |
| `user_skill` | string | One of `"Beginner"`, `"Some experience"`, `"Experienced"` — matches the frontend quick-reply values exactly (`apps/frontend/app/chat/page.tsx`) |
| `tools_available` | string[] | Tools/equipment the user says they have on hand; `[]` if none mentioned |
| `hazards` | string[] | Zero or more tags from the hazard taxonomy below; `[]` if genuinely none |
| `risk_level` | int 1–5 | Matches the backend's `risk_assessments.risk_level` column (`apps/backend/schemas/assessment.py`) — 1=safest, 5=most dangerous. **This is the field the classifier actually trains against.** |
| `risk_label` | string | Human-readable mirror of `risk_level`, one of the 5 below — kept for readability only, must always agree with `risk_level` |
| `professional_category` | string \| null | One of the professional-category tags below, or `null` if risk level doesn't warrant one (typically levels 1–2) |
| `suggested_ppe` | string[] | PPE items a competent person would use for this task; `[]` only for genuinely no-PPE tasks. **Dataset-only naming** — the live backend/frontend still use `required_ppe` (see note below) |
| `followup_questions` | object[] | **Variable-length** — zero or more `{field, question, answer}` objects: one per safety-critical hazard confirmation relevant to this task, plus (separately) one per tool the task needs whenever `tools_available` is unknown. Mirrors the backend's real `field`/`question` shape (`schemas/job.py`'s `FollowupPrompt`) and default phrasing (`ai/rule_engine/llm_assist.py`'s `_DEFAULT_FOLLOWUP_QUESTIONS`) for the hazard ones. See below for `field`/`answer` semantics of both kinds. |

### `followup_questions` — field and answer semantics

**Not every example needs the same number of entries** — most have 0, some have 1, and a task that touches multiple hazards (e.g. a wall removal near a gas line) can have 2+. Don't pad examples with irrelevant follow-ups just to make the list non-empty, and don't force every category to have exactly one.

**If `task_text` already addresses the question — with a yes, a no, *or an explicit "I don't know"* — don't also add a `followup_questions` entry for it.** A real system wouldn't (and shouldn't) re-ask a question the user already responded to unprompted, and "I'm not sure" is still a response, not silence — re-asking the identical question would just get the same "I don't know" again. `followup_questions` should only ever represent a genuinely **unaddressed** topic, one `task_text` says nothing about at all.

- `"...I already switched off the breaker and checked it's dead with a voltage tester"` and `"...remove a load-bearing brick wall..."` (states the wall IS load-bearing) → answered yes/no directly → `followup_questions: []`.
- `"...remove a wall between the kitchen and living room, not sure if it's load-bearing"` → this also already answers the question (with "unconfirmed"), just as much as a yes or no would — asking it again would be pointless → `followup_questions: []`. The escalated `risk_level`/`structural_collapse` hazard tag alone already captures the safety consequence of that "unconfirmed" state; no separate Q&A needs modeling.
- Plain `"install a ceiling fan in my bedroom"` (no mention of isolation at all) → the topic never comes up → **this** is the genuine open question → `followup_questions` with `answer: null`.

The general "not sure what tools I have on hand" wording is treated differently from a specific "not sure if X" statement: it's a *blanket* disclaimer about an unspecified inventory, not a direct answer to "do you have a voltage tester specifically" — so a `tool_available:<tool>` follow-up for one particular tool still represents a genuinely open, unaddressed question and correctly keeps `answer: null`.

`answer` is `true`, `false`, or `null` in the schema, but given the rule above, every `followup_questions` entry actually present in this dataset ends up with `answer: null` — any case where the answer was actually known (confirmed, denied, or explicitly "unsure") gets folded into `task_text`/`hazards`/`risk_level` directly instead, per the rule above, so it never appears as a followup at all. `true`/`false` remain valid for a different scenario this dataset doesn't currently model: `task_text` says nothing on the topic, but a distinct later follow-up round (not part of the initial description) resolved it — worth adding a few examples of that shape during expansion for completeness, if useful.

Currently-established `field` values (matching the live placeholder's hardcoded fields — extend this set once Phase 5's real catalog covers more hazards, e.g. a fall-height/stable-footing confirmation for roofing):

- `power_isolated` — relevant whenever the task involves **working on or cutting into fixed wiring/circuits**, regardless of the task's `category` (e.g. it applies to the HVAC thermostat-wiring and tiling wall-chasing examples too, not just `category: "electrical"` — hazard-driven, not category-driven). It is **not** triggered merely by using a corded power tool near water or by any incidental `electrical_shock` risk: "isolate the circuit at the breaker" is a meaningless instruction when the shock risk comes from a wet tile saw's own supply rather than from a circuit you're about to touch. Tasks like that carry their own hazards (`cuts_lacerations`, `hearing_damage`) without this follow-up.
- `load_bearing_confirmed` — the question ("confirmed the wall or structure involved is NOT load-bearing?") only makes sense when the task is actually **deciding whether to remove/demolish** a wall or structural element whose load-bearing status is genuinely in question, *and* `task_text` doesn't already address that status one way or another (see the redundancy rule above — "not sure if it's load-bearing" already answers it, so that example correctly has `followup_questions: []` too, not just the confirmed-yes/no ones). It does **not** apply just because `structural_collapse` is present as a hazard tag — a foundation-wall crack *repair* (not removal) and a new deck *build* (not a removal decision at all) both have `structural_collapse` as a hazard but no "is this load-bearing?" question to resolve, since nothing is being evaluated for removal. See `"remove a wall between the kitchen and living room to create an open floor plan"` (load-bearing status never mentioned at all) for the one seed example that actually keeps this follow-up.
- `gas_line_present` — relevant only when gas proximity is genuinely **uncertain** (e.g. digging a trench, drilling into a wall where a line might be routed unseen) — a *preventive* check. It does **not** apply when the task's premise already states a gas hazard is present/active (a leaking water heater, an already-cracked heat exchanger, installing a new gas appliance) — "confirmed there is no gas line present" is a non-sequitur once gas is already an established fact in `task_text`, not an open question to resolve. Those examples correctly have `followup_questions: []` — the risk level comes straight from the `gas_leak`/`fire` hazard tags, no follow-up needed. See `"dig a small trench in my backyard..."` for the correctly-scoped usage.

`answer` is `true`, `false`, or `null` — **the distinction matters and mirrors a real bug that was found and fixed in the backend** (see `memory.md`, 2026-07-19 safety-gate bug): `null` means the question was never actually answered (the ambiguous/default case — never assume safety), while `false` means the user explicitly answered in the unsafe direction (e.g. "no, I haven't isolated the power" or "no, it's not possible right now"). Both should escalate risk, but they are not the same state, and a real implementation must not conflate "answered unsafely" with "never answered."

#### `tool_available:<tool>` — a second, distinct category of follow-up

When `tools_available` is empty/unknown (the user hasn't said what they have on hand) **and the task genuinely needs a specific tool**, add a `tool_available:<tool_name>` follow-up — field name is dynamic per tool, not from a small fixed set like the three safety-critical fields above. `question` is templated: `"Do you have a <tool> available for this task?"`. `answer` uses the same `true`/`false`/`null` convention.

This is a **different kind of follow-up** from the safety-critical ones above — don't conflate them:

- **Purely functional tools** (a screwdriver, a wrench) — not having one blocks the task or means the user improvises, but for a low-risk task this doesn't change `risk_level` itself, it's informational for the recommendation. See `"replace a light switch cover plate..., not sure what tools I have on hand"` — `tool_available:screwdriver`, `risk_level` stays `1`.
- **Safety-relevant tools** (a non-contact voltage tester) — not having one means the user has no way to actually verify a safety-critical condition themselves (e.g. `power_isolated`), so it can legitimately co-occur alongside that safety-critical follow-up on the same example, as a second, related question — not a replacement for it. See `"install a ceiling fan..., not sure what tools I have on hand"` — both `power_isolated` and `tool_available:voltage_tester` appear together.

Don't invent a `tool_available:<tool>` follow-up for every tool mentioned in every example — only add one when `tools_available` is genuinely unknown/unstated for that example (mirrors real conversational uncertainty, same "don't assume" principle as the hazard follow-ups) and the tool in question actually matters for how the task should be done.

**Note on `required_ppe` vs `suggested_ppe`:** the dataset schema uses `suggested_ppe` (softer framing — the app recommends, it can't enforce PPE use). The already-built backend model/API/frontend (`apps/backend/models/risk_assessment.py`, `schemas/recommendation.py`, `RiskCard.tsx`, etc.) still use `required_ppe` — that's a deliberate scope decision, not an oversight: renaming the live DB column/API contract/frontend types is a separate cross-stack change, not done as part of this dataset work. Revisit consistency (rename one way or the other) as a dedicated task later.

**Note on PPE vs. confirmed power/gas isolation:** don't hardcode "electrical/gas work never needs PPE once isolated" as a blanket rule — the system is deliberately built to never assume safety absent explicit confirmation (`rules.md` §4, the `power_isolated` follow-up question). The conversational flow should be: **recommend isolating power first; if that's confirmed done, PPE/risk can drop; if isolation isn't possible or isn't confirmed, fall back to requiring PPE (insulated gloves) as the mitigation instead** — isolation and PPE are alternative mitigations, not both-or-nothing. Capture this as a **set of paired examples** per electrical/gas seed:
1. **Isolation genuinely never addressed in `task_text`** (a live `followup_questions` entry with `answer: null`) → **`risk_level: 5`, `suggested_ppe: []`** (see the escalation rule immediately below — this is the strongest case, stronger than a stated-but-unsafe answer, since not knowing rules out nothing).
2. **Isolation explicitly confirmed** in `task_text` → lower risk_level, shock-related PPE (`insulated_gloves`) dropped, non-electrical hazards like `fall_from_height` stay, `followup_questions: []` (redundancy rule — already answered).
3. **Isolation explicitly stated as not possible** (e.g. locked panel, shared circuit, landlord-controlled) but PPE/tester used as the stated mitigation → a *known*, not an *unknown*, state → stays at a middle risk_level (not escalated to 5, since the answer is known and a real mitigation is described), `suggested_ppe` explicitly includes `insulated_gloves` + a tester, `followup_questions: []` (redundancy rule — already answered, just answered unsafely).

See the four `"install a ceiling fan"` entries in `seed_examples.json` for this exact pattern — write more sets like this for other electrical/gas seeds during expansion. **This also matters for Phase 5**: the current Phase 6 placeholder rule engine (`ai/rule_engine/rules.py`'s `_SAFETY_CRITICAL_FOLLOWUPS`) only escalates a missing/falsy safety-critical follow-up to level 4, and doesn't distinguish "explicitly answered unsafely" (case 3 above, arguably level 3-4) from "never addressed at all" (case 1, now `risk_level: 5` in this dataset) — the placeholder should be revisited to match this once Phase 5 replaces it (see the `risk_level: 5` escalation rule below, and `memory.md`).

**Escalation rule: any example with an unanswered (`answer: null`) safety-critical follow-up (`power_isolated`, `load_bearing_confirmed`, `gas_line_present`) must have `risk_level: 5`.** This directly follows `CLAUDE.md`'s non-negotiable rule — "missing safety-critical follow-up answers escalate risk, treat as worst plausible case, never assume safety" — applied literally: not knowing whether a safety-critical condition holds means the worst plausible case can't be ruled out, so it's escalated to the maximum, not just to "professional required." This does **not** apply to `tool_available:<tool>` follow-ups (those are about capability, not hazard severity) or to hazard-confirmation follow-ups that already have a non-null answer (those are known states — see the redundancy rule above — and are scored on their own merits, which can land anywhere on the scale). This is a stronger policy than the current Phase 6 placeholder implements (see the Phase 5 note above).

### 9 locked task categories

`electrical`, `plumbing`, `carpentry`, `masonry`, `painting`, `tiling`, `hvac`, `roofing`, `general`

### 5 risk levels

**`risk_level` answers one question: what competence does THIS TASK demand?**

It is a property of the task and nothing else. It does **not** vary with who is
asking. The same job carries the same `risk_level` whether the person describing
it is a beginner or a professional — what changes is the *advice they are given*,
which is computed afterwards by comparing this level against their stated skill
(`apps/backend/ai/rule_engine/competence.py`), not baked into the label.

| `risk_level` | `risk_label` | Competence the task demands |
|---|---|---|
| 1 | `safe_diy` | Anyone. No relevant experience needed. |
| 2 | `diy_with_supervision` | Anyone, provided someone more experienced is on hand. |
| 3 | `professional_recommended` | Some relevant experience. A competent DIYer *could* do it; a pro is advisable. |
| 4 | `professional_required` | A licensed/qualified professional. Not for any DIYer, however experienced. |
| 5 | `dangerous` | **Nobody — this is not a DIY task at all.** |

#### Level 5 is not "the top of the ladder"

Levels 1–4 are a competence ladder: each step demands more of the person. **Level
5 is not the next rung.** It means the task is outside the scope of "who should
attempt this" entirely — an active emergency (a suspected gas escape, a sparking
conductor, a wall visibly moving) where the correct action is evacuate and call
for help, or work that is legally restricted regardless of skill.

Concretely: level 5 is the one tier where **the user's experience is irrelevant**.
An experienced professional who smells gas should still leave the building. Never
label an example 5 because it is "very hard" or "needs a real expert" — that is
level 4. Reserve 5 for *nobody does this by hand right now*.

**`risk_level: 5` examples should always have `suggested_ppe: []`.** At this tier the correct action is "stop and call a professional / emergency services," not "here's the PPE to handle it yourself" — recommending PPE for an active emergency (e.g. a sparking live wire) could be read as encouraging hands-on mitigation, which contradicts the do-not-attempt framing. Keep `hazards`/`professional_category` populated as normal; only `suggested_ppe` is forced empty at this tier.

#### `user_skill` is an annotation, not a label input

Every row still carries a `user_skill`, because `task_text` is written in a real
person's voice and that person has some level of experience. But it must **not**
influence `risk_level`, and the validator enforces this statistically (see
"Skill/label independence" below).

This rule exists because the opposite happened. The original seed data chose
`user_skill` "to fit the narrative" of each example — an experienced narrator for
a professional-tier job, a beginner for a simple one. The result, measured on
2026-08-01 across all 555 rows: 77 of the 85 `Experienced` rows (91%) were level
4, and there was not a single `Experienced` example at level 1, 2 or 3. The
classifier learned exactly that, and returned level 4 for an experienced user
changing a light bulb while returning level 1 for a beginner rewiring a consumer
unit. `user_skill` had become a proxy for the answer.

Skill-based escalation has not been lost — it lives in the rule engine, where it
is deterministic and unit-tested (`Rule.requires_skill`,
`electrical_work_by_beginner`, `srs.md` §9), exactly as follow-up escalation
does. The classifier's job is to judge the task; the engine's job is to judge the
match between task and person.

#### Skill/label independence

`python ml/validate_dataset.py` fails the dataset if `user_skill` and
`risk_level` are statistically dependent. Practical guidance when authoring:

- Pick `risk_level` from the task **first**, without looking at `user_skill`.
- Then pick a `user_skill` that is plausible for someone typing that sentence —
  and across a batch, vary it. A beginner can ask about a level-4 job (that is
  precisely the user this product exists for); an experienced person can ask
  whether a level-1 job is worth doing themselves.
- If you find yourself reaching for `Experienced` *because* the task is hard,
  stop. That is the confound re-forming.

### Hazard taxonomy (extend if a real seed example needs a tag not listed)

`electrical_shock`, `fall_from_height`, `structural_collapse`, `gas_leak`, `buried_utility_strike`, `fire`, `chemical_exposure`, `cuts_lacerations`, `respiratory_hazard`, `asbestos_exposure`, `water_damage`, `burns`, `heavy_object_handling`, `hearing_damage`, `confined_space`, `none`

`none` is exclusive — it cannot be combined with any other tag (the validator enforces this).

Note: `gas_leak` means gas is actually present/leaking/being connected (an active hazard, stated as fact in `task_text`). `buried_utility_strike` means the risk is *accidentally hitting* an unknown buried line (digging, trenching) — proximity is uncertain, nothing has actually leaked. Don't conflate the two: an active leak and the risk of causing one someday are different hazards with different urgency.

`asbestos_exposure` is tracked separately from the general `respiratory_hazard` tag because it drives a different recommendation (licensed removal, not just a dust mask) — typically pair the two.

### PPE vocabulary

`safety_glasses`, `work_gloves`, `insulated_gloves`, `rubber_gloves`, `dust_mask`, `respirator_mask`, `safety_harness`, `hearing_protection`, `knee_pads`, `steel_toe_boots`, `hard_hat`

Use `dust_mask` for nuisance dust and `respirator_mask` where the hazard is a vapour, solvent, fibre, or asbestos — they are not interchangeable. Extend this list if a real example needs an item not covered, and update `ml/validate_dataset.py` to match.

### Professional categories

`electrician`, `plumber`, `carpenter`, `mason`, `structural_engineer`, `roofer`, `hvac_technician`, `general_contractor`, `null` (for risk levels 1–2, no professional needed)

Levels 1–2 must have `null`; levels 3–5 must name one (both enforced by the validator). Use `structural_engineer` rather than a trade whenever the core question is whether the structure can safely be altered at all, and `general_contractor` when the task spans trades or has no single obvious specialist.

## Current composition

256 examples. `python ml/validate_dataset.py` prints the live breakdown; as of the expansion:

| Category | n | | `risk_level` | n |
|---|---|---|---|---|
| electrical | 36 | | 1 — safe_diy | 62 |
| plumbing | 32 | | 2 — diy_with_supervision | 52 |
| carpentry | 30 | | 3 — professional_recommended | 53 |
| general | 30 | | 4 — professional_required | 45 |
| hvac | 28 | | 5 — dangerous | 44 |
| masonry / painting / roofing / tiling | 25 each | | | |

No class is smaller than ~17% of the largest, so no resampling should be needed for the Phase 3 baseline. 21 examples carry a `followup_questions` entry (22 questions total).

Deliberate near-duplicates: three pairs of examples share a base task and differ only in what `task_text` states (the `"install a ceiling fan"` set, the two `"remove a wall between the kitchen and living room"` variants, the two `"light switch cover plate"` variants). These exist specifically to teach the model that the *stated information* — not the task type — drives the follow-up and risk outcome. Preserve them through the train/val/test split by keeping each pair in the same split, or they will leak.

## Reviewing an example

1. Does `risk_level`/`risk_label` match how a competent tradesperson would judge it? (Cross-check `srs.md` §9's rule catalog for the safety-critical ones — gas, live electrical, load-bearing, height, water+electricity.)
2. Are `hazards` complete — not missing an obvious one, and not over-tagged with one that doesn't fit (see the `gas_leak` vs `buried_utility_strike` note above)?
3. Is `task_text` phrased naturally, the way a real non-expert would type it (not a textbook description)?
4. Does each `followup_questions` entry survive all three scoping rules — genuinely unaddressed in `task_text`, the right field for the situation, and the question's wording actually answerable for this task?

## Next steps

1. Template-based variation generation (paraphrase/parameterize seeds to multiply coverage)
2. Weak-labeling rules for obvious cases (auto-label unambiguous template variants)
3. Standards-based review of a sample of high-risk-labeled examples (OSHA Focus Four, electrical/building codes, PPE sheets — see `memory.md`'s provisional Phase 1 resolution, no live supervisor available)
4. Train/val/test split → `train.json` / `val.json` / `test.json` (keep the deliberate near-duplicate pairs above in the same split)

Exit check (`phases.md` Phase 2): ≥500 labeled examples total, reviewed sample shows acceptable label quality with a documented agreement rate.
