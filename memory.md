# Memory Log — BuildSafe AI

This file is a **living record** of what has actually been done, kept in sync with reality — not a plan (that's `phases.md`). Update it every time a task is completed, a decision is made, or a file is meaningfully changed. Anyone (or any AI agent) picking up the project should be able to read this file top to bottom and know exactly where things stand without re-reading the whole codebase.

## How to Update This File

- Add an entry under the current phase every time you finish a checklist item from `phases.md`.
- Log decisions (not just tasks) — e.g., "chose FastAPI over NestJS because ML lives in Python."
- If something was started but not finished, say so explicitly (`IN PROGRESS`, not silently omitted).
- Never delete history — append. If something is reversed, add a new entry noting the reversal; don't erase the old one.
- This file was reset to a fresh baseline on 2026-07-18 — prior session-by-session history was folded into the reference docs it actually belongs in (`design.md` now fully specifies the frontend implementation; `prd.md`/`architecture.md`/`rules.md`/`phases.md` carry the product/scope decisions). Start logging new work below as it happens.

---

## Project Status Snapshot

| Field | Value |
|---|---|
| Current phase | Phase 0 — Project Setup |
| Last updated | 2026-07-18 |
| Overall status | Backend/repo scaffolding not started. A complete, verified frontend reference implementation exists at `chat-ui/` (React 19 + Vite + TypeScript + Tailwind v4 + Motion) — fully specified in `design.md`, which is the authoritative source for rebuilding or extending the frontend. |

## Phase Progress

### Phase 0 — Project Setup
- [ ] Repo structure created (`apps/web`, `apps/api`, `ml/`, `docs/`, `infra/`)
- [ ] Postgres + pgvector running locally
- [ ] `.env.example` documented
- [ ] Lint/format configured
- Status: **Not started**

### Frontend UI Design (ahead of Phase 7, design-only — see `design.md`)
- [x] Auth (login/register) and the full task-intake → risk-assessment chat flow built as a real React app in `chat-ui/`, matching `design.md` exactly.
- Status: **Reference implementation complete and documented in `design.md`.** Not yet wired to a real backend (Phase 1-6 haven't started) and not yet the real `apps/web` per `architecture.md`.

### Phase 1 — Research & Scope Finalization
- Status: **Not started**

### Phase 2 — Dataset Creation
- Status: **Not started**

### Phase 3 — Baseline ML Model
- Status: **Not started**

### Phase 4 — Improved ML Model
- Status: **Not started**

### Phase 5 — Safety Rule Engine
- Status: **Not started**

### Phase 6 — Backend APIs
- Status: **Not started**

### Phase 7 — Frontend Chat Flow
- Status: **Not started for real code.** Design/UI groundwork done — see Frontend UI Design above and `design.md`.

### Phase 8 — Testing & Deployment
- Status: **Not started**

### Phase 9 — Documentation & Final Demo
- Status: **Not started**

---

## Files Touched Log

_(Append one row per meaningful change — new file, major edit, deletion.)_

| Date | File(s) | Change | Phase |
|---|---|---|---|

## Decisions Log

_(Append one entry per non-trivial decision — tech choices, scope cuts, rule changes.)_

| Date | Decision | Reasoning |
|---|---|---|

## Bugs Found & Fixed

_(Real runtime bugs caught during verification, not just typos — kept here since they're non-obvious enough to bite again if similar patterns are reused. Known pitfalls specific to the current frontend implementation are documented inline in `design.md`'s ⚠️ callouts instead of here.)_

| Date | Bug | Root cause | Fix |
|---|---|---|---|

## Known Issues / Open Threads

_(Anything left dangling — a TODO, a bug, a question for the supervisor.)_

## Open Questions Carried from `prd.md`

- Minimum dataset size and expert-review process — **unresolved**
- Acceptable false-negative rate for high-risk classes — **unresolved**
