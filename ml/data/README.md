# ml/data — Dataset Creation (Phase 2)

This directory holds the labeled dataset used to train the Phase 3/4 ML risk classifier. See `phases.md` Phase 2 and `srs.md` §12 for the source spec.

## Files

- `seed_examples.json` — hand-written seed examples, **the file to review/expand right now**. Currently a small scaffold (a handful of examples per category, spanning multiple risk levels) — needs to grow to 200–300 hand-written examples before template expansion/weak-labeling.
- `train.json` / `val.json` / `test.json` — final split, generated later (70/15/15) once the full ≥500-example dataset exists. **Not created yet.**

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

**If `task_text` already states the answer, don't also add a `followup_questions` entry for it** — a real system wouldn't (and shouldn't) ask a question the user already answered unprompted in their initial description; representing that as a follow-up Q&A implies a redundant round-trip that shouldn't happen. E.g. `"...I already switched off the breaker and checked it's dead with a voltage tester"` and `"...remove a load-bearing brick wall..."` (which already states the wall IS load-bearing) both correctly have `followup_questions: []` — the answer is fully conveyed through `task_text` itself (which the classifier reads directly) and through `risk_level`/`hazards`/`suggested_ppe`, with no need to also model a Q&A exchange that wouldn't occur. Contrast with `"...not sure if it's load-bearing"` or `"...not sure what tools I have"`, where the text itself states the answer is *unknown* — that's a genuine open question, correctly kept with `answer: null`.

Currently-established `field` values (matching the live placeholder's hardcoded fields — extend this set once Phase 5's real catalog covers more hazards, e.g. a fall-height/stable-footing confirmation for roofing):

- `power_isolated` — relevant whenever `electrical_shock` is a hazard, regardless of the task's `category` (e.g. it applies to the HVAC thermostat-wiring example and the tiling-near-outlets example too, not just `category: "electrical"` — hazard-driven, not category-driven)
- `load_bearing_confirmed` — the question ("confirmed the wall or structure involved is NOT load-bearing?") only makes sense when the task is actually **deciding whether to remove/demolish** a wall or structural element whose load-bearing status is genuinely in question. It does **not** apply just because `structural_collapse` is present as a hazard tag — a foundation-wall crack *repair* (not removal) and a new deck *build* (not a removal decision at all) both have `structural_collapse` as a hazard but no "is this load-bearing?" question to resolve, since nothing is being evaluated for removal. Both correctly have `followup_questions: []`; only genuine wall/structure-removal examples (e.g. `"remove a wall between the kitchen and living room..."`) use this field.
- `gas_line_present` — relevant only when gas proximity is genuinely **uncertain** (e.g. digging a trench, drilling into a wall where a line might be routed unseen) — a *preventive* check. It does **not** apply when the task's premise already states a gas hazard is present/active (a leaking water heater, an already-cracked heat exchanger, installing a new gas appliance) — "confirmed there is no gas line present" is a non-sequitur once gas is already an established fact in `task_text`, not an open question to resolve. Those examples correctly have `followup_questions: []` — the risk level comes straight from the `gas_leak`/`fire` hazard tags, no follow-up needed. See `"dig a small trench in my backyard..."` for the correctly-scoped usage.

`answer` is `true`, `false`, or `null` — **the distinction matters and mirrors a real bug that was found and fixed in the backend** (see `memory.md`, 2026-07-19 safety-gate bug): `null` means the question was never actually answered (the ambiguous/default case — never assume safety), while `false` means the user explicitly answered in the unsafe direction (e.g. "no, I haven't isolated the power" or "no, it's not possible right now"). Both should escalate risk, but they are not the same state, and a real implementation must not conflate "answered unsafely" with "never answered."

#### `tool_available:<tool>` — a second, distinct category of follow-up

When `tools_available` is empty/unknown (the user hasn't said what they have on hand) **and the task genuinely needs a specific tool**, add a `tool_available:<tool_name>` follow-up — field name is dynamic per tool, not from a small fixed set like the three safety-critical fields above. `question` is templated: `"Do you have a <tool> available for this task?"`. `answer` uses the same `true`/`false`/`null` convention.

This is a **different kind of follow-up** from the safety-critical ones above — don't conflate them:

- **Purely functional tools** (a screwdriver, a wrench) — not having one blocks the task or means the user improvises, but for a low-risk task this doesn't change `risk_level` itself, it's informational for the recommendation. See `"replace a light switch cover plate..., not sure what tools I have on hand"` — `tool_available:screwdriver`, `risk_level` stays `1`.
- **Safety-relevant tools** (a non-contact voltage tester) — not having one means the user has no way to actually verify a safety-critical condition themselves (e.g. `power_isolated`), so it can legitimately co-occur alongside that safety-critical follow-up on the same example, as a second, related question — not a replacement for it. See `"install a ceiling fan..., not sure what tools I have on hand"` — both `power_isolated` and `tool_available:voltage_tester` appear together.

Don't invent a `tool_available:<tool>` follow-up for every tool mentioned in every example — only add one when `tools_available` is genuinely unknown/unstated for that example (mirrors real conversational uncertainty, same "don't assume" principle as the hazard follow-ups) and the tool in question actually matters for how the task should be done.

**Note on `required_ppe` vs `suggested_ppe`:** the dataset schema uses `suggested_ppe` (softer framing — the app recommends, it can't enforce PPE use). The already-built backend model/API/frontend (`apps/backend/models/risk_assessment.py`, `schemas/recommendation.py`, `RiskCard.tsx`, etc.) still use `required_ppe` — that's a deliberate scope decision, not an oversight: renaming the live DB column/API contract/frontend types is a separate cross-stack change, not done as part of this dataset work. Revisit consistency (rename one way or the other) as a dedicated task later.

**Note on PPE vs. confirmed power/gas isolation:** don't hardcode "electrical/gas work never needs PPE once isolated" as a blanket rule — the system is deliberately built to never assume safety absent explicit confirmation (`rules.md` §4, the `power_isolated` follow-up question). The conversational flow should be: **recommend isolating power first; if that's confirmed done, PPE/risk can drop; if isolation isn't possible or isn't confirmed, fall back to requiring PPE (insulated gloves) as the mitigation instead** — isolation and PPE are alternative mitigations, not both-or-nothing. Capture this as a **three-way set of paired examples** per electrical/gas seed:
1. **Isolation not stated at all** (the ambiguous/default case — never assume safety) → higher risk_level, full PPE required.
2. **Isolation explicitly confirmed** in `task_text` → lower risk_level, shock-related PPE (`insulated_gloves`) dropped, non-electrical hazards like `fall_from_height` stay.
3. **Isolation explicitly not possible** (e.g. locked panel, shared circuit, landlord-controlled) but PPE/tester used as the stated mitigation → risk_level stays at the same tier as case 1 (the hazard is still real), but `suggested_ppe` explicitly includes `insulated_gloves` + a tester, since that's the recommended fallback mitigation.

See the four `"install a ceiling fan"` entries in `seed_examples.json` for this pattern (risk_level/suggested_ppe vary across all four; only the "isolation not stated" and "tools unknown" variants also carry a `followup_questions` entry — the other two already state the answer in `task_text`, so per the redundancy rule above they correctly have `followup_questions: []`) — write more triples like this for other electrical/gas seeds during expansion. **This also matters for Phase 5**: the current Phase 6 placeholder rule engine (`ai/rule_engine/rules.py`'s `_SAFETY_CRITICAL_FOLLOWUPS`) only has a binary `power_isolated` true/false escalation — it can't yet express "isolation not possible, but mitigated via PPE" as a distinct, less-escalated outcome from "isolation simply unanswered." Worth designing for explicitly when Phase 5 replaces the placeholder (logged in `memory.md`).

### 9 locked task categories

`electrical`, `plumbing`, `carpentry`, `masonry`, `painting`, `tiling`, `hvac`, `roofing`, `general`

### 5 risk levels

| `risk_level` | `risk_label` | Meaning |
|---|---|---|
| 1 | `safe_diy` | Safe DIY — no special precautions beyond common sense |
| 2 | `diy_with_supervision` | DIY with Supervision — doable but benefits from a second pair of hands / basic guidance |
| 3 | `professional_recommended` | Professional Recommended — a competent DIYer *could* do it, but a pro is advisable |
| 4 | `professional_required` | Professional Required — should not be attempted without a licensed professional |
| 5 | `dangerous` | Dangerous / Do Not Attempt |

**`risk_level: 5` examples should always have `suggested_ppe: []`.** At this tier the correct action is "stop and call a professional / emergency services," not "here's the PPE to handle it yourself" — recommending PPE for an active emergency (e.g. a sparking live wire) could be read as encouraging hands-on mitigation, which contradicts the do-not-attempt framing. Keep `hazards`/`professional_category` populated as normal; only `suggested_ppe` is forced empty at this tier.

### Hazard taxonomy (extend if a real seed example needs a tag not listed)

`electrical_shock`, `fall_from_height`, `structural_collapse`, `gas_leak`, `buried_utility_strike`, `fire`, `chemical_exposure`, `cuts_lacerations`, `respiratory_hazard`, `water_damage`, `burns`, `none`

Note: `gas_leak` means gas is actually present/leaking/being connected (an active hazard, stated as fact in `task_text`). `buried_utility_strike` means the risk is *accidentally hitting* an unknown buried line (digging, trenching) — proximity is uncertain, nothing has actually leaked. Don't conflate the two: an active leak and the risk of causing one someday are different hazards with different urgency.

### Professional categories

`electrician`, `plumber`, `carpenter`, `mason`, `structural_engineer`, `roofer`, `hvac_technician`, `general_contractor`, `null` (for risk levels 1–2, no professional needed)

## What "review" means for the seed scaffold

For each example in `seed_examples.json`:
1. Does `risk_level`/`risk_label` actually match how a competent tradesperson would judge this task? (Cross-check against `srs.md` §9's rule catalog for the safety-critical ones — gas, live electrical, load-bearing, height, water+electricity.)
2. Are `hazards` complete — not missing an obvious one?
3. Is `task_text` phrased naturally, the way a real non-expert user would type it (not a textbook description)?

Then: **write 15–30 more examples per category** (aim for good spread across all 5 risk levels within each category, not just the extremes) until the file has 200–300 total. Category+risk-level combinations that don't make physical sense (e.g. `painting` at `risk_level 5`) can be left thin or skipped — don't force artificial examples just to fill a grid cell.

## Next steps after seed review

1. Template-based variation generation (paraphrase/parameterize seeds to multiply coverage)
2. Weak-labeling rules for obvious cases (auto-label unambiguous template variants)
3. Standards-based review of a sample of high-risk-labeled examples (OSHA Focus Four, electrical/building codes, PPE sheets — see `memory.md`'s provisional Phase 1 resolution, no live supervisor available)
4. Train/val/test split → `train.json` / `val.json` / `test.json`

Exit check (`phases.md` Phase 2): ≥500 labeled examples total, reviewed sample shows acceptable label quality with a documented agreement rate.
