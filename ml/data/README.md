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
  "suggested_ppe": ["insulated_gloves", "safety_glasses"]
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

**Note on `required_ppe` vs `suggested_ppe`:** the dataset schema uses `suggested_ppe` (softer framing — the app recommends, it can't enforce PPE use). The already-built backend model/API/frontend (`apps/backend/models/risk_assessment.py`, `schemas/recommendation.py`, `RiskCard.tsx`, etc.) still use `required_ppe` — that's a deliberate scope decision, not an oversight: renaming the live DB column/API contract/frontend types is a separate cross-stack change, not done as part of this dataset work. Revisit consistency (rename one way or the other) as a dedicated task later.

**Note on PPE vs. confirmed power/gas isolation:** don't hardcode "electrical/gas work never needs PPE once isolated" as a blanket rule — the system is deliberately built to never assume safety absent explicit confirmation (`rules.md` §4, the `power_isolated` follow-up question). The conversational flow should be: **recommend isolating power first; if that's confirmed done, PPE/risk can drop; if isolation isn't possible or isn't confirmed, fall back to requiring PPE (insulated gloves) as the mitigation instead** — isolation and PPE are alternative mitigations, not both-or-nothing. Capture this as a **three-way set of paired examples** per electrical/gas seed:
1. **Isolation not stated at all** (the ambiguous/default case — never assume safety) → higher risk_level, full PPE required.
2. **Isolation explicitly confirmed** in `task_text` → lower risk_level, shock-related PPE (`insulated_gloves`) dropped, non-electrical hazards like `fall_from_height` stay.
3. **Isolation explicitly not possible** (e.g. locked panel, shared circuit, landlord-controlled) but PPE/tester used as the stated mitigation → risk_level stays at the same tier as case 1 (the hazard is still real), but `suggested_ppe` explicitly includes `insulated_gloves` + a tester, since that's the recommended fallback mitigation.

See the three `"install a ceiling fan"` entries in `seed_examples.json` for this exact pattern — write more triples like this for other electrical/gas seeds during expansion. **This also matters for Phase 5**: the current Phase 6 placeholder rule engine (`ai/rule_engine/rules.py`'s `_SAFETY_CRITICAL_FOLLOWUPS`) only has a binary `power_isolated` true/false escalation — it can't yet express "isolation not possible, but mitigated via PPE" as a distinct, less-escalated outcome from "isolation simply unanswered." Worth designing for explicitly when Phase 5 replaces the placeholder (logged in `memory.md`).

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

### Hazard taxonomy (extend if a real seed example needs a tag not listed)

`electrical_shock`, `fall_from_height`, `structural_collapse`, `gas_leak`, `fire`, `chemical_exposure`, `cuts_lacerations`, `respiratory_hazard`, `water_damage`, `burns`, `none`

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
