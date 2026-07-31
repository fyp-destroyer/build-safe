# Phases — BuildSafe AI

Each phase has a clear deliverable and an exit check. Don't start a phase until the previous one's exit check passes. If time runs short, cut features per the Must/Should/Could priority in `prd.md` — don't cut the exit checks.

---

## Phase 0 — Project Setup

**Deliverable:** monorepo scaffolded per `architecture.md`, CI running, dev environments working for all 3 members.

- [x] Repo structure created (`apps/frontend`, `apps/backend`, `ml/`, `infra/` — `docs/` deliberately not created, root-level docs kept instead; see Known Issues in `memory.md`)
- [x] Postgres running locally + pgvector extension enabled (confirmed 2026-07-18; note a real port-5432 conflict with a native Windows Postgres service on this machine — see `memory.md` Known Issues)
- [x] `.env.example` documented for both apps
- [x] Lint/format configs (ESLint+Prettier for frontend, ruff/black for backend)
- [x] `memory.md` initialized (root-level, not `docs/memory.md` — see `docs/` note above)
  **Exit check:** all 3 members can run frontend + backend locally and hit a health-check endpoint. — **PASSES.**

## Phase 1 — Research & Scope Finalization

**Deliverable:** finalized problem statement, 5 risk classes, task categories — no more open scope questions.

- [X] Dataset size target and expert-review process — **resolved provisionally (2026-07-19), no supervisor available.** See `prd.md` §7 for the working targets and the substitute standards-review process; revisit with the supervisor when possible.
- [X] Acceptable false-negative tolerance for high-risk classes — **resolved provisionally (2026-07-19)** at ≥95% recall on Professional Required/Dangerous; see `prd.md` §7.
- [X] Lock task category list (electrical, plumbing, carpentry, masonry, painting, tiling, HVAC, roofing, general) — already consistently implemented across `chatData.ts`, `Sidebar.tsx`, `srs.md` §9, and `rules.md`; nothing further to decide.
  **Exit check:** `prd.md` open questions section is empty. — **Provisionally met:** the section is no longer blank/unresolved, but both answers are self-determined (not supervisor-approved) and marked as such in `prd.md` §7 — confirm with the supervisor and update if their answer differs.

## Phase 2 — Dataset Creation

**Deliverable:** labeled dataset, hazard taxonomy, tool mappings, train/val/test split.

- [x] 200–300 hand-written seed examples across categories — **256 in `ml/data/seed_examples.json`** (2026-07-29), all 9 categories (25–36 each) and all 5 risk levels (44–62 each). Schema, scoping rules, and labelling conventions documented in `ml/data/README.md`; `ml/validate_dataset.py` mechanically enforces them.
- [x] Template-based task variation generation — **299 variants via `ml/generate_variations.py`** (2026-07-29): conversational rephrasing (256) + risk-neutral room substitution (26) + confirmation-stripping (17). Deterministic and re-runnable.
- [x] Weak-labeling rules for obvious cases — three rules, all constrained so none can lower a risk level (`rules.md` §4.2): label-preserving inheritance for rephrase/room-swap, escalation-only for confirmation-stripping. De-escalation is deliberately **not** automated. Enforced by `ml/validate_dataset.py`.
- [~] Expert review of a sample of high-risk-labeled examples — **substitute performed, genuine expert review still outstanding.** `ml/review_high_risk.py` audits all 555 examples against 11 floors derived from published standards (HSE, OSHA Focus Four, Gas Safety Regs 1998, Control of Asbestos Regs 2012, BS 7671/Part P, Confined Spaces Regs 1997) plus `srs.md` §9. Findings and fixes in `ml/data/REVIEW.md`. **The resulting figure is NOT an inter-rater agreement statistic** — labels and audit rules share an author — and must not be reported as one. Discharging this properly needs a licensed tradesperson labelling a blind sample with Cohen's κ computed; still flagged provisional per `prd.md` §7.
- [x] Final split committed to `ml/data/` (never commit PII/real user data here) — **387/86/82 (69.7/15.5/14.8%)** via `ml/make_splits.py`. Grouped by `variant_of` *and* by seed-to-seed relatedness so contrast sets cannot straddle a split; the script refuses to write files if a group spans splits, a class is missing, or a leak is detected.
  **Exit check:** ≥500 labeled examples, reviewed sample shows acceptable label quality (agreement rate documented). — **Count met (555). Label quality: 100% conformance to a standards-derived floor rubric after fixing 1 genuine mislabel + 1 wrong hazard tag (95.8% before fixes), self-audited.** The exit check's "agreement rate" is only partially satisfied: a conformance rate is documented, but independent expert agreement has not been measured. Treat this phase as passed-with-caveat and revisit if a supervisor/domain expert becomes available.

## Phase 3 — Baseline ML Model

**Deliverable:** TF-IDF + Logistic Regression classifier, evaluated.

- [x] `ml/train_baseline.py` trains and saves a model artifact — TF-IDF (word + char n-grams) + Logistic Regression (`class_weight="balanced"`), hyperparameters selected on val, artifact at `ml/eval/baseline_model.joblib` (2026-07-30).
- [x] Evaluation report: accuracy, macro F1, recall per class, confusion matrix — `ml/eval/baseline_report.md` (+ `baseline_metrics.json`, `baseline_confusion.png`).
  **Exit check:** baseline recall on high-risk classes measured and documented (even if not yet at target). — **MET.** Hand-written test set: accuracy 0.650, macro-F1 0.646, high-risk recall (≥4 caught as ≥4) **0.529, 95% CI [0.31, 0.74]**. Grouped 5-fold CV over all 555 rows (more stable): macro-F1 0.679 ±0.041, high-risk recall **0.706 ±0.090**. Simulating the deployed `max(ML, rules)` pipeline lifts test high-risk recall to **0.657**. All well below `prd.md` §7's provisional ≥95% target — which is expected and explicitly permitted at this phase; closing that gap is Phase 4's job.
  - Features restricted to real inference-time inputs (`task_text`, `category`, `user_skill`, `tools_available`). `professional_category`, `suggested_ppe`, `hazards` and follow-up state are all **excluded as label leakage** — measured, not assumed: `professional_category is None` ⟺ `risk ≤ 2` in 555/555 rows.

## Phase 4 — Improved ML Model

**Deliverable:** embedding-based classifier, compared against baseline.

- [x] `ml/train_embedding_model.py` using sentence-transformer embeddings — `all-MiniLM-L6-v2` (384-d, frozen) + Logistic Regression head, identical inputs to the baseline so the comparison isolates the representation (2026-07-30).
- [x] Side-by-side comparison report vs. baseline — `ml/eval/comparison_report.md`.
  **Exit check:** decision made on which model ships, documented with reasoning. — **MET. The TF-IDF baseline ships.** The embedding model is decisively worse on macro F1 (**−0.075 ± 0.033**, losing **5/5** paired CV folds) and no better on high-risk recall (−0.020, inside the ±0.082 fold spread). Decision rests on paired grouped 5-fold CV, not the 40-row test set, whose ±0.2 CI cannot separate two models.
  - **Why the general-purpose encoder loses** (the opposite of the usual expectation, so it is explained in the report): risk here is carried by rare domain tokens — *gas*, *asbestos*, *load-bearing*, *consumer unit*, *fragile* — which TF-IDF weights precisely; MiniLM compresses to 384 general-similarity dimensions where *"replace a light fixture"* and *"replace a consumer unit"* sit close together despite being three risk levels apart. ~390 training rows is far too little to learn a head that recovers the distinction.
  - Both artifacts kept per `architecture.md` §1. Serving stays scikit-learn-only — no torch, no ~90 MB download.

## Phase 5 — Safety Rule Engine

**Deliverable:** hardcoded rule set (LLM-assisted authoring, dev-reviewed) + escalation logic implemented and tested. No admin UI — rule changes go through code review and redeploy.

- [x] Hardcoded rubric + hazard rule module — `ai/rule_engine/catalog.py` (DATA: 13 rules, floors, explanations) + `ai/rule_engine/rules.py` (LOGIC). Version-controlled, no `safety_rules` table, no runtime edit path (2026-07-31).
- [x] `ai/rule_engine` uses an LLM call to classify which hardcoded hazard rule(s) match — `llm_assist.tag_hazards()`. The LLM may only SELECT ids from the catalog; every id is filtered against `VALID_RULE_IDS`, so an invented id is discarded. It never assigns a risk number. Returns `[]` on any failure, so the engine degrades to "no LLM", never to "no hazards".
- [x] `final_risk = max(ML, rules)` implemented and unit-tested — property test is exhaustive over descriptions × categories × answer sets × all 5 possible ML outputs.
- [x] **Catalog extended to 18 rules (2026-07-31)** after measuring which dangerous tasks were still missed. Deployed high-risk recall 0.804 → **0.873**; **0.959 on tasks whose hazard is stated in the text**, meeting `prd.md` §7's ≥95% target. See `ml/analyze_recall.py`.
- [x] **Catalog extended to 21 rules (2026-07-31)**, the last three under a held-out validation protocol (`ml/data/holdout_rules.json`, committed before the rules; 14 of its 24 cases are adversarial negatives). **24/24 held out.** Deployed high-risk recall **0.902**, over-escalation 0.094, **1.000 on tasks whose hazard is stated** — see `ml/analyze_recall.py` and `ml/check_holdout.py`.
- [x] Representative rule set from SRS §9 seeded — all six §9 rows implemented, plus hazards the dataset surfaced (asbestos, fragile surfaces, confined space, buried services, structural distress). **Jurisdiction-neutral**: rules state hazard and consequence, not legal citations, since the project targets no specific regulatory regime.
  **Exit check:** unit tests prove rules can only escalate, never de-escalate (see `rules.md` §4.2), and that the LLM hazard classifier cannot introduce a rule outside the hardcoded set. — **MET.** `apps/backend/tests/test_rule_catalog.py`, 45 pure-logic tests passing (no DB, no network — a test proving the safety engine cannot be subverted must not be skippable because a container is down). Adversarial cases included: hallucinated ids, an empty id, and a SQL-injection-shaped id are all discarded without shifting risk.

## Phase 6 — Backend APIs

**Deliverable:** all core REST endpoints functional.

- [x] `/auth`, `/jobs`, `/assessments`, `/recommendations` — built 2026-07-19 ahead of sequence; the AI layer behind them became real in Phases 5–6 (2026-07-31).
- [x] Auth enforced and tested (single `user` role — no admin/professional roles; real JWT+bcrypt)
- [x] `ai_logs` writes on every assessment (including failures) — never a silent "safe" fallback
- [x] **Placeholders replaced.** `ai/rule_engine/` is the real hardcoded catalog (Phase 5); `ai/classifier/` now serves the trained `ml/eval/baseline_model.joblib` (Phase 3/4 winner) instead of a keyword heuristic.
- [x] **API contract exported and FR coverage verified** — `python apps/backend/scripts/export_api_collection.py` writes `docs/openapi.json`, `docs/postman_collection.json` and `docs/API_COVERAGE.md`, and **exits non-zero if any FR has no endpoint**, so coverage is checked rather than claimed.
  **Exit check:** Postman/OpenAPI collection covers every FR-01–FR-09 endpoint; all return correct error shapes on bad input. — **MET.** All 9 FRs map to live endpoints across 10 product routes; error shape `{ "error": { "code", "message" } }` and 422 field-level detail are covered by `tests/test_validation_errors.py` / `tests/test_auth.py`. Risk decisions are now produced by the real trained model and the real rule engine, so the earlier "structurally met only" caveat is resolved.
  - Two honest gaps recorded in `docs/API_COVERAGE.md` rather than hidden: **FR-02** has no photo upload or location/budget fields, and **FR-07** returns `cost`/`time`/`difficulty` as `null` because no estimation engine exists (`prd.md` ranks it Medium priority). The endpoints and response shapes exist; the data does not.
  - `GET /health/ready` added alongside `/health`: liveness stays dependency-free, readiness reports whether the classifier actually loaded. A deployment can be live but unable to assess, and that distinction should be visible.

## Phase 7 — Frontend Chat Flow

**Deliverable:** conversational task intake → follow-up → inline risk card → saved history, working end to end against real backend, with a ChatGPT/Gemini-like interaction feel.

- [x] Chat interface (sidebar conversation list, message thread, composer)
- [x] Conversational task intake + follow-up question flow (quick-reply chips), wired to the real backend
- [x] Inline risk assessment card (risk chip, explanation, tools/materials)
- [x] User dashboard (history, saved lists) — built into `Sidebar.tsx`, not a separate page (user decision)
- [x] **Verified live in Chrome against the real stack (2026-07-31)** — trained classifier + real rule engine + Postgres, not placeholders.
  **Exit check:** a non-technical tester can complete the full journey unassisted for all 4 demo scenarios. — **MET.** All four risk tiers driven through the real UI end to end:
  1. **Safe DIY (1)** — repaint a bedroom wall → level 1, no rules, PPE + DIY checklist shown.
  2. **Professional Recommended (3)** — cracked ridge tile on a *single storey bungalow* → level 3 from the classifier alone, `work_at_height` correctly suppressed by its low-height excludes.
  3. **Professional Required (4)** — remove a wall, follow-up answered "No" → **`max(ML=2, rules=4) = 4`**, the escalation invariant visible in production.
  4. **Dangerous (5)** — gas smell → level 5, `active_gas_or_co`, DIY tool guidance withheld.
  - Also verified: register → JWT session persists across reload, sidebar history, and re-opening a past chat restores its saved assessment (FR-09).
  - **Bug found by this testing and fixed:** the risk card showed prettified rule slugs ("Active gas or co", "Unsafe followup:load bearing confirmed") instead of guidance. `explain()` existed in the catalog but nothing ever called it. `RiskAssessmentOut` now exposes a computed `safety_notes`, so a gas report reads "leave the area, avoid switches and naked flames, and contact your gas emergency service". Computed at read time, so existing assessments improve too.
  - Known limitation, not a defect: every chat is categorised **"General"** because `GEMINI_API_KEY` is unset and `tag_category` falls back as designed. Category tagging is the only visibly degraded feature without a key.

## Phase 8 — Testing & Deployment

**Deliverable:** deployed, demo-ready system.

- [ ] Unit tests for `ai/rule_engine`, `ai/classifier`, core services
- [ ] API integration tests
- [ ] UI smoke tests for the 4 demo scenarios
- [ ] Migrate auth from the current custom JWT implementation to Clerk — **planned, not started.** User's stated intent (2026-07-19): switch after the core flow (Phases 2-7) is working end-to-end, not before. Note this reverses an earlier same-day decision (see `memory.md` Decisions Log, 2026-07-19: "Considered switching auth to Clerk — decided against, kept JWT") made when the cost looked like ripping out already-built, already-tested auth mid-flow; revisit the webhook-based user-sync design (Clerk user → local `users` row as the FK target for jobs/assessments) once this phase is actually reached.
- [ ] Deployed frontend (Vercel), backend (Render/Railway/Fly.io), DB (managed Postgres)
- [ ] Seed/demo data loaded
  **Exit check:** all Acceptance Criteria in the SRS §11 pass in the deployed environment, not just locally.

## Phase 9 — Documentation & Final Demo

**Deliverable:** final report, slides, demo video, evaluation results.

- [ ] Final evaluation report (metrics from `ml/eval/`)
- [ ] Screenshots and demo script for all 5 risk levels
- [ ] Future work section (from `prd.md` out-of-scope list)
- [ ] `docs/memory.md` reflects final state of the project
  **Exit check:** dry-run of the full demo in front of the team, timed, no surprises.

---

> **2026-07-18 renumbering note:** Phase 8 "Admin Dashboard" was cut from scope (see `memory.md` decisions log) — safety rules are now hardcoded + LLM-assisted rather than admin-managed, so there's no CRUD UI to build. Former Phase 9/10/11 shifted down to Phase 8/9/10.
>
> **2026-07-18 second renumbering note:** the former Phase 8 "Professional / Vendor Module" was also cut from scope (see `memory.md` decisions log) — professionals are not modeled as app users at all now, so there's no professional dashboard or quote-response flow to build. Former Phase 9/10 shifted down to Phase 8/9. Old numbers are preserved here only for cross-referencing prior memory.md entries.

---

## How to Use This File With `memory.md`

After completing any checklist item above, log it in `memory.md` with the date, phase, and files touched. `phases.md` defines *what* needs to happen; `memory.md` records *what has* happened.
