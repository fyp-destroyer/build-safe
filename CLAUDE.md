# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

This repo currently contains **only planning/spec docs** — no application code. The previous implementation (a `buildsafe-ai/` monorepo with a FastAPI backend and a React reference frontend at `chat-ui/`) was deliberately wiped in the "starting from scratch" commit; only the seven markdown docs at the repo root survive. There is no `package.json`, no build tooling, and no test suite yet — when work resumes, it starts by scaffolding per `architecture.md` §3 (Phase 0 in `phases.md`).

Read these seven files in this order before making any non-trivial change — they are the actual spec, not background reading:

1. **`prd.md`** — what BuildSafe AI is: a platform that decides *whether* a DIY/construction task is safe to attempt (not how to do it), producing one of 5 risk levels plus tool/material/PPE recommendations. Read this for scope (§4 lists what's explicitly out of scope) and the one key product principle (§6).
2. **`architecture.md`** — tech stack, high-level data flow, and the target monorepo layout (`apps/frontend`, `apps/backend`, `ml/`, `docs/`, `infra/`). §4 walks the exact request path for a single risk assessment.
3. **`rules.md`** — hard boundaries, not style preferences. §4 (AI/LLM Boundaries) is non-negotiable and gates every PR touching `ai/` (checklist in §5).
4. **`srs.md`** — full functional/non-functional requirements, data model, and the safety rule catalog (§9). Authoritative for acceptance criteria (§11).
5. **`design.md`** — complete frontend implementation spec (design tokens, component-by-component breakdown, motion conventions) for a React 19 + Vite + TypeScript + Tailwind v4 + Motion reference app. This is the spec to rebuild the frontend from — it does not currently exist in the tree.
6. **`phases.md`** — the sequential build plan (Phase 0 through 9), each with an exit check that gates the next phase. Currently on Phase 0 per `memory.md`.
7. **`memory.md`** — living log of what has actually been done vs. planned. Update it whenever a `phases.md` checklist item completes or a non-trivial decision is made; never delete history, only append.

## The one rule that overrides everything else

**The LLM never decides risk level.** `final_risk = max(ML classifier output, rule engine output)`. The rule engine's rubric (5 risk levels, escalation thresholds) is hardcoded in `ai/rule_engine/` — never admin-editable or LLM-editable at runtime. There is no `admin` role and no runtime-editable rules table by design (`architecture.md` §5, `prd.md` §4). The LLM's only permitted jobs: phrasing follow-up questions, turning triggered rules into templated explanation text, and tagging which hardcoded hazard rule(s) match a task's text (never inventing a new rule or assigning a risk number itself). The rule engine can only escalate risk, never de-escalate — if this constraint is ever at risk of being violated by a change, stop and flag it rather than proceeding. Full details: `rules.md` §4.

Two more fail-loud requirements worth internalizing before touching `ai/`:
- Missing safety-critical follow-up answers escalate risk (treat as worst plausible case), never assume safety.
- AI pipeline failures must set `assessment_status = "failed"` and block the DIY recommendation — never silently fall back to a "safe" result.

## Planned architecture (not yet scaffolded)

- **Frontend**: Next.js (App Router) + TypeScript + Tailwind CSS, deployed to Vercel.
- **Backend**: FastAPI (Python) — chosen so the ML pipeline shares a runtime with the API.
- **Database**: PostgreSQL + pgvector (semantic tool/material/task retrieval).
- **ML**: scikit-learn baseline (TF-IDF + Logistic Regression) vs. sentence-transformer + classifier, compared in an eval report; both kept.
- **LLM layer**: Google Gemini API **or** Groq (OpenAI-compatible), selected by `LLM_PROVIDER` = `gemini` | `groq` | `auto`; template- and schema-constrained prompts only (structured JSON output, never free text) — see rule above. Switched from Anthropic 2026-07-19; Groq added as an alternative 2026-07-31 (both user's explicit choice; see `memory.md` decisions log). All provider code lives behind `ai/llm/client.py:generate_structured` — that is the only module in the codebase permitted to call an LLM, and every reply is validated against a Pydantic schema before any caller sees it, so the provider in use can never change a risk decision.
- **Auth**: JWT, single `user` role — no `admin` or `professional` roles exist in this product.

Non-negotiable flow rule (`architecture.md` §2): the frontend never calls the LLM directly; the backend never returns a risk level that skipped `max(ML, rules)`.

## Working conventions

- Frontend: App Router / Server Components (not Pages Router), Tailwind core utilities only, `zod` for schema validation, `react-hook-form` only for the auth forms (task intake is conversational, not a form), `motion` (formerly framer-motion) for chat/sidebar/composer animation, a thin `lib/api.ts` fetch wrapper instead of axios.
- Backend: FastAPI + Pydantic v2, SQLAlchemy (async) + Alembic migrations (no raw SQL in route handlers), `passlib`/`python-jose` for auth, `pytest` — do not skip tests on `ai/rule_engine` or `ai/classifier`, they're safety-critical.
- Error handling: never fail silently. Structured `{ "error": { "code", "message" } }` on every API error; 422 with field-level detail on Pydantic validation errors; every `ai/` exception logged to `ai_logs` with input context even on failure.
- Follow `phases.md` sequentially — each phase has an exit check; don't start the next phase until the current one's exit check passes. If cutting scope under time pressure, cut features per the Must/Should/Could priority in `prd.md`, never the exit checks themselves.
- After completing any `phases.md` checklist item or making a non-trivial decision, log it in `memory.md` (date, phase/decision, files touched) — that file is what lets a fresh session pick up context without re-deriving it.
