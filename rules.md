# Rules — BuildSafe AI

Conventions and hard boundaries for anyone (human or AI agent) writing code in this repo.

## 1. Libraries — Use vs. Avoid

### Frontend
| Use | Avoid | Why |
|---|---|---|
| Next.js App Router, Server Components where possible | Pages Router | New code should follow one pattern |
| Tailwind CSS (core utility classes only) | Ad-hoc inline styles, random CSS-in-JS libs | Consistency with `design.md` tokens |
| `zod` for form/schema validation | Hand-rolled validation | Single source of truth for shapes shared with backend schemas |
| `react-hook-form` for the remaining multi-field forms (auth) | Uncontrolled forms with manual state | Task intake itself is now conversational, not a form, but the auth forms still benefit |
| `motion` (formerly `framer-motion`) for chat message/sidebar/composer animation | Ad-hoc CSS transitions for anything gesture- or sequence-driven | Matches the ChatGPT/Gemini-like feel `design.md` specifies; respects `prefers-reduced-motion` |
| Convex React hooks (`useQuery`/`useMutation`/`useAction`), or the `useConvex()` client via `lib/convexApi.ts` | Axios, hand-rolled fetch wrappers | Convex handles transport, auth and caching; the adapter exists only to keep the chat flow's promise-based shape |
| Clerk's **headless** hooks (`useSignIn`/`useSignUp`) | Clerk's prebuilt `<SignIn />` / `<SignUp />` components | `design.md` is a requirement; the auth screens must not change appearance |

### Backend (Convex)
| Use | Avoid | Why |
|---|---|---|
| Convex `query` / `mutation` with `v.*` argument validators | Unvalidated args, `v.any()` for user input | Type safety at the trust boundary |
| Convex `action` for anything doing network I/O (LLM calls) | Network calls from a query or mutation | Not merely a convention — the runtime forbids it, which is what makes "the LLM never decides risk" structural |
| `requireUser` + ownership scoping at the top of every user-facing function | Trusting an id passed from the client | Returns *not found*, never *forbidden*, so existence is not leaked |
| Zod for validating every LLM reply before use | Trusting model output | A provider must never be able to inject a value the schema didn't allow |
| Vitest for `convex/ai/ruleEngine` | Skipping these tests | These modules are safety-critical — see §4 |
| scikit-learn (offline, in `ml/`) for the classifier, exported to JSON | Training custom neural nets from scratch; hand-editing the exported weights | Scope discipline; the export is verified against scikit-learn in CI |

### General
- No new dependency without checking it's actively maintained and has no known critical CVEs.
- Prefer the standard library over a package for anything trivial (date formatting, simple string ops).
- Pin versions in `package.json` and `ml/requirements.txt` — no floating `latest`. The scikit-learn pin matters especially: `ml/eval/baseline_model.joblib` was fitted with 1.8.0, and the export script must run against that version.

## 2. Error Handling

- **Never fail silently.** Every API error returns a structured JSON error (`{ "error": { "code": ..., "message": ... } }`), logged server-side with enough context to reproduce it.
- **Backend validation errors** (Pydantic) return `422` with field-level detail — the frontend must surface which field failed, not a generic "something went wrong."
- **AI pipeline failures are not silent fallbacks to "safe."** If the classifier or rule engine throws, the job assessment must fail loudly and visibly (`assessment_status = "failed"`), never default to a low-risk result. A failed assessment blocks the user from seeing a DIY recommendation until it's resolved.
- **Frontend** wraps all data-fetching in error boundaries with a visible retry action; no blank screens on failure.
- Log every exception in `ai/` modules to `ai_logs` with input context, even on failure — needed for debugging safety-critical misfires.

## 3. Security Boundaries

- All non-public endpoints require a valid JWT; role check happens in middleware, not ad hoc in each route.
- Only one role exists: `user`. There is no `admin` role (safety rules are hardcoded, not runtime-managed) and no `professional` role (professionals are not app users — see `prd.md` §4).
- Uploaded task photos: validate file type/size server-side before storage; never trust client-side validation alone.
- No secrets (API keys, DB credentials) in source. Use environment variables + `.env` (gitignored) + a documented `.env.example`.

## 4. AI / LLM Boundaries — Non-Negotiable

These rules exist because this product makes safety-relevant decisions. They are not style preferences.

1. **The LLM never decides risk level.** Risk level is always `max(ML classifier output, rule engine output)`, and the rule engine's rubric (the 5 risk levels, escalation thresholds) is hardcoded in code — never admin-editable, never LLM-editable, at runtime. The LLM's only jobs are: (a) phrasing follow-up questions, (b) turning triggered rules/factors into readable explanation text, and (c) **hazard classification** — tagging which of the hardcoded hazard rules match a given task's text (e.g. "does this mention live wiring with no confirmed isolation?"). Hazard classification is a yes/no match against a fixed, code-reviewed rule set; the LLM is never asked to "decide if this is safe" or to invent a new rule outside that set.
2. **The rule engine can only escalate, never de-escalate.** If the ML model says "Safe DIY" and a rule fires (however it was matched — keyword or LLM-classified), the rule wins. There is no code path where the rule engine lowers risk below the ML prediction.
3. **Explanations must be templated, not freely generated.** The explanation text is built by inserting the actual triggered rule names / model features into a template. The LLM must not be allowed to state a safety fact (e.g., "this voltage is safe to touch") that didn't come from the rule engine or classifier output.
4. **Missing information escalates risk, it never assumes safety.** If a safety-critical follow-up question goes unanswered, treat it as the worst plausible case for that field, not the average or best case.
5. **No hallucinated citations or safety standards.** If the system references a standard (e.g., OSHA guidance), it must come from the hardcoded, dev-reviewed rule/reference set — never invented at inference time, and never sourced from a runtime admin edit (there is no admin edit path).
6. **Every classification is logged.** Model input, model output, confidence, and triggered rules go to `ai_logs` for every single assessment, no sampling — this is what makes a disputed classification auditable.
7. **Confidence is surfaced, not hidden.** Low-confidence ML predictions are shown as such in `ai_logs` even if the rule engine ultimately determines the final risk — needed for later model evaluation.

## 5. Code Review Checklist (apply to every PR touching `ai/`)

- [ ] Does this change ever let a rule *lower* risk? (Should be impossible — reject if so.)
- [ ] Is the LLM call template-constrained, or could it emit unconstrained safety claims?
- [ ] Is the failure path fail-loud, not fail-safe-looking?
- [ ] Is the input/output logged to `ai_logs`?
- [ ] Are there tests covering the specific rule(s) this PR touches (see `phases.md` testing phase)?
