# Phases — BuildSafe AI

Each phase has a clear deliverable and an exit check. Don't start a phase until the previous one's exit check passes. If time runs short, cut features per the Must/Should/Could priority in `prd.md` — don't cut the exit checks.

---

## Phase 0 — Project Setup
**Deliverable:** monorepo scaffolded per `architecture.md`, CI running, dev environments working for all 3 members.
- [ ] Repo structure created (`apps/web`, `apps/api`, `ml/`, `docs/`, `infra/`)
- [ ] Postgres running locally + pgvector extension enabled
- [ ] `.env.example` documented for both apps
- [ ] Lint/format configs (ESLint+Prettier for web, ruff/black for api)
- [ ] `docs/memory.md` initialized (see that file)
**Exit check:** all 3 members can run frontend + backend locally and hit a health-check endpoint.

## Phase 1 — Research & Scope Finalization
**Deliverable:** finalized problem statement, 5 risk classes, task categories — no more open scope questions.
- [ ] Confirm dataset size target and expert-review process with supervisor
- [ ] Confirm acceptable false-negative tolerance for high-risk classes
- [ ] Lock task category list (electrical, plumbing, carpentry, masonry, painting, tiling, HVAC, roofing, general)
**Exit check:** `prd.md` open questions section is empty.

## Phase 2 — Dataset Creation
**Deliverable:** labeled dataset, hazard taxonomy, tool mappings, train/val/test split.
- [ ] 200–300 hand-written seed examples across categories
- [ ] Template-based task variation generation
- [ ] Weak-labeling rules for obvious cases
- [ ] Expert review of a sample of high-risk-labeled examples
- [ ] Final split committed to `ml/data/` (never commit PII/real user data here)
**Exit check:** ≥500 labeled examples, reviewed sample shows acceptable label quality (agreement rate documented).

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
- [ ] `/auth`, `/jobs`, `/assessments`, `/recommendations`
- [ ] Auth enforced and tested (single `user` role — no admin/professional roles)
- [ ] `ai_logs` writes on every assessment (including failures)
**Exit check:** Postman/OpenAPI collection covers every FR-01–FR-12 endpoint; all return correct error shapes on bad input.

## Phase 7 — Frontend Chat Flow
**Deliverable:** conversational task intake → follow-up → inline risk card → saved history, working end to end against real backend, with a ChatGPT/Gemini-like interaction feel.
- [ ] Chat interface (sidebar conversation list, message thread, composer)
- [ ] Conversational task intake + follow-up question flow (asked as chat messages, quick-reply chips)
- [ ] Inline risk assessment card (risk chip, explanation, tools/materials, cost/time) rendered as an assistant message
- [ ] User dashboard (history, saved lists)
**Exit check:** a non-technical tester can complete the full journey unassisted for all 4 demo scenarios.

## Phase 8 — Testing & Deployment
**Deliverable:** deployed, demo-ready system.
- [ ] Unit tests for `ai/rule_engine`, `ai/classifier`, core services
- [ ] API integration tests
- [ ] UI smoke tests for the 4 demo scenarios
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
