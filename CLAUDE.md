# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

The app is built and runs on three managed services: **Vercel** (Next.js 16
frontend), **Convex** (database *and* all backend functions, in TypeScript), and
**Clerk** (auth). Nothing is self-hosted — there is no Docker, no Postgres, and
no Python service to run.

Phases 0-7 are complete. Phase 8 (testing & deployment) is in progress: the Clerk
migration is done, deployment is not.

`apps/backend/` (FastAPI + SQLAlchemy + Alembic) was **removed on 2026-08-03**
when the backend moved to Convex. Its safety-critical logic was not rewritten by
hand — it was ported and then verified equivalent row-by-row against the original
before deletion (see `architecture.md` §1.1). `ml/` still holds the offline
training pipeline and is still the source of the shipped classifier; it is just
no longer loaded at runtime.

To run it locally you need two processes and no database:

```bash
cd apps/frontend
npx convex dev     # pushes convex/ to the dev deployment, writes .env.local
npm run dev        # Next.js
npm run verify     # safety tests + both port-equivalence gates
```

Read these seven files in this order before making any non-trivial change — they
are the actual spec, not background reading:

1. **`prd.md`** — what BuildSafe AI is: a platform that decides *whether* a
   DIY/construction task is safe to attempt (not how to do it), producing one of
   5 risk levels plus tool/material/PPE recommendations. Read this for scope (§4
   lists what's explicitly out of scope) and the one key product principle (§6).
2. **`architecture.md`** — tech stack, data flow, repo layout. §1.1 records why
   the stack changed and what was done to make that safe; §4 walks the exact
   path of a single risk assessment.
3. **`rules.md`** — hard boundaries, not style preferences. §4 (AI/LLM
   Boundaries) is non-negotiable and gates every PR touching `convex/ai/`
   (checklist in §5).
4. **`srs.md`** — full functional/non-functional requirements, data model, and
   the safety rule catalog (§9). Authoritative for acceptance criteria (§11).
5. **`design.md`** — complete frontend implementation spec (design tokens,
   component-by-component breakdown, motion conventions). The migration to
   Clerk deliberately changed **no** markup or styling: Clerk is driven through
   its headless hooks so this spec still describes the shipped UI exactly.
6. **`phases.md`** — the sequential build plan, each phase gated by an exit check.
7. **`memory.md`** — living log of what has actually been done vs. planned.
   Update it whenever a `phases.md` item completes or a non-trivial decision is
   made; never delete history, only append.

## The one rule that overrides everything else

**The LLM never decides risk level.** `finalRisk = max(ML classifier output, rule engine output)`. The rule engine's rubric (5 risk levels, escalation thresholds) is hardcoded in `apps/frontend/convex/ai/ruleEngine/` — never admin-editable or LLM-editable at runtime. There is no `admin` role and no runtime-editable rules table by design (`architecture.md` §5, `prd.md` §4). The LLM's only permitted jobs: phrasing follow-up questions, turning triggered rules into templated explanation text, and tagging which hardcoded hazard rule(s) match a task's text (never inventing a new rule or assigning a risk number itself). The rule engine can only escalate risk, never de-escalate — if this constraint is ever at risk of being violated by a change, stop and flag it rather than proceeding. Full details: `rules.md` §4.

Two more fail-loud requirements worth internalizing before touching `convex/ai/`:
- Missing safety-critical follow-up answers escalate risk (treat as worst plausible case), never assume safety. An absent answer is NOT the same as an answer of "no", and missing scores higher.
- AI pipeline failures must set the assessment `status` to `"failed"` and block the DIY recommendation — never silently fall back to a "safe" result. An `aiLogs` row is written on every attempt, including failures, with no sampling.

## Architecture

- **Frontend**: Next.js 16 App Router + TypeScript + Tailwind v4, on Vercel.
- **Backend + database**: Convex. Queries and mutations are transactional and
  pure; anything touching the network must be an **action**. That split is load
  bearing — it makes it structurally impossible for the risk-bearing code to call
  an LLM.
- **Auth**: Clerk, single `user` role — no `admin` or `professional` roles exist
  in this product. Authorization is ownership scoping, not roles: every Convex
  function starts with `requireUser` and returns *not found* (never *forbidden*)
  for another user's row, so existence is never leaked.
- **ML**: scikit-learn TF-IDF + Logistic Regression, trained offline in `ml/`,
  exported to `convex/ai/classifier/model.json` by `ml/export_model_json.py` and
  evaluated in TypeScript. Verified identical to scikit-learn to 1.55e-15.
- **LLM layer**: Google Gemini **or** Groq, selected by `LLM_PROVIDER` =
  `gemini` | `groq` | `auto`. All provider code lives behind
  `convex/ai/llm/client.ts` — the only module in the codebase permitted to call
  an LLM — and every reply is Zod-validated before any caller sees it, so the
  provider in use can never change a risk decision.

Non-negotiable flow rule (`architecture.md` §2): the frontend never calls the LLM
directly; the backend never returns a risk level that skipped `max(ML, rules)`.

### Two generated files — never hand-edit

- `convex/ai/ruleEngine/catalog.ts` — generated by `tools/generate_catalog_ts.py`.
- `convex/ai/classifier/model.json` — generated by `ml/export_model_json.py`.

Both are checked by CI against frozen outputs from the original Python
implementation (`tools/compare_*.mjs`). Editing either by hand will either fail
those gates or, worse, quietly change a safety decision.

## Working conventions

- **Frontend**: App Router / Server Components (not Pages Router), Tailwind core
  utilities only, `zod` for schema validation, `react-hook-form` only for the auth
  forms (task intake is conversational, not a form), `motion` (formerly
  framer-motion) for chat/sidebar/composer animation. No axios.
- **Auth in the UI**: Clerk's **headless hooks** (`useSignIn` / `useSignUp`),
  never its prebuilt `<SignIn />` components. The design in `design.md` is a
  requirement; Clerk is only the mechanism. Clerk v7's methods RETURN
  `{ error }` rather than throwing, so check the result — a `try/catch` alone
  will silently treat a failed sign-in as success.
- **Backend (Convex)**: queries and mutations are pure and transactional;
  anything doing network I/O must be an **action**. Validate every argument with
  `v.*` validators. Do not skip the tests on `convex/ai/ruleEngine` — they are
  safety-critical (`rules.md` §1).
- **Ownership**: every user-facing function begins with `requireUser` and scopes
  by owner, returning *not found* rather than *forbidden* for another user's row.
- **Error handling**: never fail silently. A Convex function throws with
  user-facing wording, which reaches the client as `Error.message`; every
  exception in `convex/ai/` is logged to `aiLogs` with input context even on
  failure.
- **Next.js 16**: read `apps/frontend/AGENTS.md`. This version has breaking
  changes from what you may remember — e.g. `middleware.ts` is deprecated and
  renamed `proxy.ts`. Check `node_modules/next/dist/docs/` before writing code
  and heed deprecation notices.
- **Local dev**: use `npm run dev` (it passes `--webpack`; Turbopack crashes on
  the primary dev machine).
- Follow `phases.md` sequentially — each phase has an exit check; don't start the
  next phase until the current one's exit check passes. If cutting scope under
  time pressure, cut features per the Must/Should/Could priority in `prd.md`,
  never the exit checks themselves.
- After completing any `phases.md` checklist item or making a non-trivial
  decision, log it in `memory.md` (date, phase/decision, files touched) — that
  file is what lets a fresh session pick up context without re-deriving it.
  Append; never delete history.
