# Risk-level rubric

How a `risk_level` in `seed_examples.json` is arrived at, and what can and cannot
be cited in support of it. Sources referenced by `id` live in `sources.json`.

## Why this document exists

`ml/data/REVIEW.md` audits labels against floors implied by published standards.
It reaches 65 of 256 seeds. The other 191 rest on the author's judgement, and the
honest claim in REVIEW.md is *"conformance to a standards-derived floor rubric,
self-audited"* — not *"these labels are correct."*

The obvious fix is to find a standard for the other 191. **That fix is not
available.** No authoritative body publishes a DIY competence scale. Everything
that grades DIY task difficulty is a retailer, a contractor's marketing page, or
a home-improvement blog (`sources.json` → `rejected` → `diy-difficulty-blogs`).
Regulators do not write in these units: they answer *"who is legally permitted to
do this work?"*, which is a different question and only has an answer at the top
of the scale.

So `risk_level` is not sourced directly. It is **computed from two sourced inputs
by a function published here**:

```
risk_level = max(severity_floor, restriction_floor)
```

The inputs carry citations. The function does not, and does not pretend to. What
this buys is that the label is *reproducible*: given the same two inputs, anyone
applying this table gets the same number, and any disagreement is located in a
specific cited input rather than in an unexaminable judgement call.

## Axis 1 — Severity

**What is the worst credible outcome for a person doing this task with normal
precautions?** Not the worst imaginable outcome; not the outcome if everything
goes wrong at once.

| Band | Worst credible outcome | Floor | Typical evidence |
|---|---|---|---|
| **S1** | Self-treating. Minor cut, bruise, splinter, sore back the next day. | 1 | `cpsc-neiss` |
| **S2** | Needs medical attention; full recovery expected. Deep laceration, chemical splash, minor burn, strain. | 2 | `cpsc-neiss`, `cpsc-power-tools-2003h054` |
| **S3** | Hospital admission, permanent impairment, or death — but controlled by normal precautions and correct equipment. | 3 | `hse-fatal-injuries`, `osha-silica-1926-1153` |
| **S4** | As S3, but **published guidance specifies engineered controls or specialist equipment** — staging, cable-locating gear, enclosure, atmosphere testing, temporary structural support — rather than care and PPE. | 4 | `hsg33`, `hsg47`, `car-2012`, `confined-spaces-regs-1997`, `approved-document-a` |

**S1–S3 grade the outcome; S4 grades controllability.** These are different
questions and conflating them was a measured bug, not a theoretical one. The first
version of this rubric capped severity at 3 on the reasoning that "a fall from a
two-storey roof can kill, but roofing is done safely every day." True — but it
meant anything dangerous for *physical* rather than *legal* reasons could not
reach 4, and since a legal restriction fires on only about a quarter of the
dataset, most genuinely severe tasks landed at 3. Measured against the hand
labels, mean delta ran **+1.00 at level 1 down to −1.59 at level 5**: monotonic,
i.e. structural.

**S4 is not "feels dangerous."** It requires a published document specifying
engineered controls. That is a factual question about a document, which is what
keeps the band citable and stops it becoming a bucket for things that merely
worry us. If no such document exists, the band is S3 and the level is 3.

## Axis 2 — Restriction

**Is this work restricted, and by what?**

| Class | Meaning | Floor | Evidence |
|---|---|---|---|
| **R0** | Unrestricted. | — | — |
| **Rw** | Fixed-wiring work on an existing circuit. Not notifiable, but the conductors may be live. | 3 | `approved-document-p`, `electrical-safety-first` |
| **R1** | Notifiable: a householder *may* do it, but it must be certified by a registered competent person or notified to building control. | 4 | `approved-document-p`, `approved-document-a` |
| **R2** | Restricted to registered, licensed or qualified persons. | 4 | `gas-safety-regs-1998`, `car-2012`, `confined-spaces-regs-1997`, `fgas-qualifications`, `approved-document-g` |
| **R3** | Active emergency. The correct action is stop, leave, and call for help. | 5 | `gas-safety-regs-1998`, `hse-fatal-injuries` |

Three things to be careful about, all easy to get wrong in a way the product would
then state to users:

- **R1 is a certification duty, not a prohibition.** Part P does not make notifiable
  work illegal for a homeowner; it requires inspection and certification. Never
  render R1 as "you are not allowed to do this." It still floors at 4, because
  completing the work lawfully requires a qualified professional in the loop —
  which is `README.md`'s definition of level 4.
- **Rw exists so level 3 has a home.** Replacing a socket like-for-like is fixed
  wiring but not notifiable. This matches `fixed_wiring_work` (floor 3) in
  `convex/ai/ruleEngine/catalog.ts`, so the dataset and the shipped engine agree.
- **R2h has been retired.** "Specialist controls are required" is a statement about
  controllability, not about law. It now lives on the severity axis as S4. Keeping
  it here made the restriction axis carry two unrelated meanings and hid the
  compression bug above.

## The table

`risk_level = max(severity_floor, restriction_floor)`

| | R0 | Rw | R1 / R2 | R3 |
|---|---|---|---|---|
| **S1** | 1 | 3 | 4 | 5 |
| **S2** | 2 | 3 | 4 | 5 |
| **S3** | 3 | 3 | 4 | 5 |
| **S4** | 4 | 4 | 4 | 5 |

## How well does it reproduce the hand labels?

**182 of 256 seeds (71.1%)**, measured 2026-08-12 by `python ml/assign_basis.py`.

| version | agreement | what changed |
|---|---|---|
| initial | 63.3% | severity capped at S3; R2h on the restriction axis |
| + S4 band | 65.2% | controllability split out of restriction |
| + broad R3 | 69.1% | emergencies were only detected for gas and sparking wires |
| + G3 / F-gas / Part A | 71.1% | plumbing and HVAC had no restriction source at all |

**Tuning stopped here deliberately.** Each step above fixed a defect identifiable
*without* looking at whether agreement improved — a missing source, a wrong
document, an axis carrying two meanings. Continuing to adjust predicates until the
rubric reproduced the hand labels would make the sourced claim circular: the
labels would simply be wearing citations. `REVIEW.md` documents this exact failure
mode ("changing a check because it flagged something is how an audit gets quietly
tuned to pass").

The remaining 74 disagreements are spread evenly across all nine categories, which
is what per-row judgement difference looks like rather than systematic bias. They
are a **review queue**, not a defect list: neither number is automatically right.

## Overrides

Two product rules sit outside the table and win over it. Both only ever escalate,
per `rules.md` §4.2.

1. **Unanswered safety-critical follow-up → 5.** An `answer: null` on
   `power_isolated`, `load_bearing_confirmed` or `gas_line_present` means the worst
   plausible case cannot be ruled out. Predates this rubric; see `README.md`.
2. **Explicit emergency language in `task_text` → 5** (R3). "I can smell gas",
   "the wall is moving", "there's sparking" — regardless of what the task would
   otherwise score.

## Ceilings, not just floors

Every rule in `review_high_risk.py` before 2026-08-12 was a floor, so the audit
could only catch under-labelling. That is the direction that matters most
(`prd.md` §7's recall target), but a floors-only audit can never show a label is
*right* — only that it is not too low. Over-labelling has a real cost too: a
product that calls everything dangerous gets ignored, which is `prd.md` §6's
stated product principle.

So the table is now read in both directions. A seed at S1/R0 must be **exactly 1**,
not "at least 1". A seed whose level exceeds its table value must carry either an
override above or an explicit documented exception — otherwise it is a defect in
the over-labelling direction and the audit reports it.

## What may and may not be claimed

**May:** *"Every risk level is a documented, deterministic function of two
externally-sourced inputs: worst-credible-outcome severity, evidenced by injury
surveillance data, and regulatory restriction, evidenced by named legislation and
tagged with the jurisdiction it applies in. The function is published."*

**May:** *"The system fails toward caution by construction: the rule engine can
only escalate, and `finalRisk = max(classifier, rules)`."*

**May not:** *"Risk levels are based on / verified against safety standards, so
they are accurate."* The severity band is a judgement about which cited outcome
applies, and no cited source assigns a level to a task. Conformance is not
correctness (`REVIEW.md` §Limitations).

**May not:** any statement that a restriction is universal. Restrictions are
jurisdiction-tagged in `sources.json` for exactly this reason — Gas Safe
registration is GB law and has no US equivalent in that form.

**Still outstanding:** no licensed tradesperson has reviewed any label. This rubric
makes the labels reproducible and traceable; it does not make them expert-validated.
Discharging that still requires an independent blind sample with Cohen's κ, per
`REVIEW.md` § "What would actually discharge this requirement".
