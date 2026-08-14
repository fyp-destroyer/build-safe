# Label Quality Review — Phase 2

Reproduce with `python ml/review_high_risk.py`. Date: 2026-07-29,
**updated 2026-08-13**.

> **2026-08-13 update.** This document describes the *floors-only* audit. It has
> since been joined by `ml/data/rubric.md`, which derives every label from cited
> severity and restriction inputs rather than only checking it is not too low, and
> by `ml/data/sources.json`, which records each source with a verification date.
> Read those first; this file remains accurate about the floors audit and its
> limitations, and its Limitations section still stands in full.
>
> Three changes were made to `review_high_risk.py` on that date:
> - **`fragile-roof-surface` cited INDG284**, which HSE's own fragile-surfaces page
>   does not reference — it appears to be a withdrawn 2008 leaflet. Now cites
>   **HSG33 paras 170-202 and GEIS5**.
> - **`electrical-work-by-beginner` retired.** It audited a floor the product no
>   longer implements: `user_skill` was removed from the product on 2026-08-02 and
>   the shipped catalog replaced that rule with `fixed_wiring_work`, floor 3 for
>   everyone. It was also the only rule keyed on `user_skill`, so the skill
>   rebalance in commit `741fcc9` made it fire on a label nobody had changed —
>   leaving this audit failing at 98.5% while this document claimed 100%.
> - **`fixed-wiring-work` added** in its place, gated on isolation not being stated
>   as confirmed. That gate is a deliberate divergence from the catalog and the
>   reason is documented at the rule.
>
> The audit is green again: **100% on both files, 0 below floor.**
>
> **The audit now checks both directions.** Every rule here defines a *floor*, so
> until 2026-08-13 it could only catch under-labelling — which meant it could
> never show a label was *right*, only that it was not too low. That limitation is
> point 5 of the Limitations section below, and it is now partly addressed.
>
> A **ceiling** bounds how far a label may exceed the level its cited evidence
> derives (`basis.rubric_level` from `ml/data/rubric.md`), with one band of slack
> for author judgement. Rows carrying a documented policy escalation — an
> unanswered safety-critical follow-up, or active emergency language — are exempt,
> since those legitimately exceed what hazards alone justify.
>
> Calibration over the 256 seeds: **slack 0 flags 31 rows, slack 1 flags 0, slack 2
> flags 0.** So the check is live rather than vacuous, and the bound is tight — the
> largest over-label anywhere in the dataset, relative to its cited evidence, is
> exactly one band.
>
> The first implementation of this check wrote its own hazard predicates and
> produced 24 flags, **all 24 of which were bugs in the check** rather than defects
> in the labels: it knew nothing about restrictions, so notifiable plumbing and
> F-gas work looked over-labelled. It was rewritten to anchor on the rubric, which
> already combines cited severity with cited restriction, rather than keep a second
> and worse copy of that logic.

## Read this first: what this review is and is not

**It is** an automated conformance audit of every label against minimum risk levels implied by published safety standards (HSE, OSHA Focus Four, Gas Safety Regulations 1998, Control of Asbestos Regulations 2012, BS 7671 / Building Regs Part P, Confined Spaces Regulations 1997) and by `srs.md` §9's own rule catalog. Every rule in `ml/review_high_risk.py` cites the standard it derives from.

**It is not an inter-rater agreement statistic, and the number below must not be reported as one.** The dataset labels and the audit rules were authored in the same session by the same author. A high conformance rate here demonstrates that the labels are internally consistent with an external rubric — it does **not** demonstrate that a licensed tradesperson would agree with them. Reporting this as "expert agreement" would misrepresent it.

`phases.md` Phase 2 asks for "expert review of a sample of high-risk-labeled examples." No domain expert was available; `prd.md` §7 records the provisional substitution of a documented-standards cross-check, pending supervisor confirmation. **This audit is that substitute, and the substitution is still unconfirmed.** See Limitations.

## Method

Rather than sampling, every one of the 555 examples was audited (sampling was unnecessary — the check is mechanical). Eleven rules each define a **floor**: the minimum `risk_level` a cited standard implies for a matching situation.

The direction that matters is **under-labelling**. A task labelled below its floor is a false negative — the failure mode `prd.md` §7 sets a ≥95% recall target against. Over-labelling is reported separately and is not treated as a defect, since escalation is always the safe direction (`rules.md` §4.2).

## Results

| | Examples matching ≥1 rule | Meet/exceed floor | Conformance |
|---|---|---|---|
| **First run (as authored)** | 71 seeds | 68 | **95.8%** |
| **After fixes** | 64 seeds | 64 | **100%** |
| **After fixes (generated)** | 73 | 73 | **100%** |

Three findings on the first run. Notably they were **three different kinds of problem**, only one of which was a bad label:

**1. Genuine mislabel — fixed.** `"paint the exterior of a two-story house using an extension ladder"` was labelled `2` (DIY with supervision). Second-storey ladder work is squarely `srs.md` §9's "height above a safe threshold" and an OSHA Focus Four fall exposure. Raised to `3`, `professional_category: general_contractor`, PPE updated to include `safety_harness`. **This is the one real label defect the audit caught.**

**2. Wrong hazard tag — fixed.** `"replace a faulty GFCI outlet in the bathroom - breaker is off and confirmed dead"` carried `water_damage`. That tag is used elsewhere for water *escaping* (burst pipe, leaking trap); a damp location is a different thing, and fitting an outlet carries no water-escape risk. Tag removed; `electrical_shock` already captured the real hazard.

**3. Audit rule too broad — rule narrowed, label left alone.** Two rules were mis-specified relative to the standards they cite:
- `water-at-live-electrics` originally fired on `electrical_shock` + `water_damage` co-occurring, but §9 describes water *actively reaching* electrics. Narrowed to require escaping-water language.
- `roof-or-height-work` fired on any mention of a roof, including a low garden outbuilding reached from a step ladder — below any meaningful height threshold. Explicitly-low contexts now excluded.

A fourth defect was found in the audit tooling itself: substring matching made `"flood"` match **flood**light, producing a false positive on an unrelated example. Matching is now word-boundary anchored.

> **On narrowing rules after seeing results:** changing a check because it flagged something is exactly how an audit gets quietly tuned to pass, so each change above is justified by the rule being wrong *relative to the standard it cites*, not by the finding being inconvenient. Both narrowed rules reduce hit counts, so as a guard against silently losing coverage, gas-related examples were re-checked by hand afterwards: all 12 remain adequately labelled, and the only one no rule fires on is already at `risk_level 5`, the maximum.

## Over-labelling review

34 seeds sit at `risk_level ≥ 4` with no standards rule firing. All were reviewed and none is a defect:

- Most are `risk_level 5` via **our own escalation rule** (an unanswered safety-critical follow-up), which the standards rules deliberately do not encode — e.g. trench digging, chasing a channel into a wall, wiring an outdoor socket.
- The rest carry hazards the eleven rules do not cover: emergent structural distress (bouncy floor with a spreading ceiling crack, a widening crack over a door, a bulging retaining wall), sewage backflow as a biohazard, and burning treated timber (arsenic/copper fume).

## Limitations

1. **Not independent.** Same author for labels and rules. This is the single biggest weakness of this review.
2. **Not a domain expert.** No licensed electrician, plumber, gas engineer or structural engineer reviewed any label. Provisional per `prd.md` §7, pending supervisor confirmation.
3. **Rules are coarse.** Eleven pattern-based rules cannot capture every hazard; only 64 of 256 seeds match any rule at all, so **75% of the dataset is unaudited by this method** and rests on the original hand-judgement alone.
4. **Jurisdiction.** Rules lean on UK regulations (Gas Safe, Part P, BS 7671). Thresholds differ elsewhere; `prd.md` does not fix a target jurisdiction.
5. **Conformance ≠ correctness.** Meeting a floor says a label is not *too low*; it does not say it is *right*.

## What would actually discharge this requirement

A licensed tradesperson independently labelling a blind sample (≥50 examples, weighted to `risk_level` 4–5), with **Cohen's κ** computed against the dataset labels. That produces a real inter-rater agreement figure. Until then, the honest claim is: *"100% conformance to a standards-derived floor rubric, self-audited; independent expert agreement not yet measured."*
