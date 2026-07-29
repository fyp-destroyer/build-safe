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
- [ ] Expert review of a sample of high-risk-labeled examples
- [ ] Final split committed to `ml/data/` (never commit PII/real user data here) — **must group by `variant_of`**: a variant shares nearly all its text with its parent, so a naive split leaks train into test.
  **Exit check:** ≥500 labeled examples, reviewed sample shows acceptable label quality (agreement rate documented). — **555 labeled examples (256 hand-written + 299 generated) as of 2026-07-29, so the count half is met.** The reviewed-sample/agreement-rate half is still outstanding.

## Phase 3 — Baseline ML Model

**Deliverable:** TF-IDF + Logistic Regression classifier, evaluated.

- [ ] `ml/train_baseline.py` trains and saves a model artifact
- [ ] Evaluation report: accuracy, macro F1, recall per class, confusion matrix
  **Exit check:** baseline recall on high-risk classes measured and documented (even if not yet at target).

## Phase 4 — Improved ML Model

**Deliverable:** embedding-based classifier, compared against baseline.

- [ ] `ml/train_embedding_model.py` using sentence-transformer embeddings
- [ ] Side-by-side comparison report vs. baseline
  **Exit check:** decision made on which model ships, documented with reasoning.

## Phase 5 — Safety Rule Engine

**Deliverable:** hardcoded rule set (LLM-assisted authoring, dev-reviewed) + escalation logic implemented and tested. No admin UI — rule changes go through code review and redeploy.

- [ ] Hardcoded rubric + hazard rule module (`ai/rule_engine/rules.py` or equivalent, version-controlled)
- [ ] `ai/rule_engine` uses an LLM call to classify which hardcoded hazard rule(s) match a job's context (hazard tagging only — never assigns a risk number)
- [ ] `final_risk = max(ML, rules)` implemented and unit-tested
- [ ] Representative rule set from SRS §9 seeded into the hardcoded module
  **Exit check:** unit tests prove rules can only escalate, never de-escalate (see `rules.md` §4.2), and that the LLM hazard classifier cannot introduce a rule outside the hardcoded set.

## Phase 6 — Backend APIs

**Deliverable:** all core REST endpoints functional.

- [x] `/auth`, `/jobs`, `/assessments`, `/recommendations` — built 2026-07-19, ahead of sequence at the user's explicit request (Phases 1-5 not yet done)
- [x] Auth enforced and tested (single `user` role — no admin/professional roles; real JWT+bcrypt)
- [x] `ai_logs` writes on every assessment (including failures) — never a silent "safe" fallback
  **Exit check:** Postman/OpenAPI collection covers every FR-01–FR-12 endpoint; all return correct error shapes on bad input. — **Wiring/shape met and independently re-verified (38/38 pytest passing).** Actual risk *decisions* are still not trustworthy: `ai/classifier/` and `ai/rule_engine/` are TEMPORARY keyword-heuristic placeholders standing in for real Phase 3-5 work, loudly marked as such in module docstrings. Must be swapped for the real ML/rule-engine before this phase's exit check is truly, not just structurally, met.

## Phase 7 — Frontend Chat Flow

**Deliverable:** conversational task intake → follow-up → inline risk card → saved history, working end to end against real backend, with a ChatGPT/Gemini-like interaction feel.

- [x] Chat interface (sidebar conversation list, message thread, composer)
- [x] Conversational task intake + follow-up question flow (asked as chat messages, quick-reply chips) — wired to the real backend 2026-07-19 (scripted `chatData.ts` demo data removed)
- [x] Inline risk assessment card (risk chip, explanation, tools/materials) rendered as an assistant message — `cost`/`time` fields not yet populated (`"Not yet available"`), pending a real cost/time engine
- [x] User dashboard (history, saved lists) — **resolved without a dedicated dashboard page**, at the user's request after reviewing and rejecting a mockup: built directly into `Sidebar.tsx` as Favourites/Chats sections instead. `app/dashboard/page.tsx` remains an intentionally untouched stub.
  **Exit check:** a non-technical tester can complete the full journey unassisted for all 4 demo scenarios. — **Not yet met.** Flow now runs against the real backend end-to-end (API-contract-level verified 2026-07-19; a live browser click-through of the real-backend version is still outstanding), but only 2 of the 4 demo scenarios exist, and risk decisions still ride on Phase 6's TEMPORARY placeholders — not truly meetable until Phases 3-5 land.

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
