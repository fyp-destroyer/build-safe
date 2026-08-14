# Architecture — CanIDIY

## 1. Tech Stack (decided)

| Layer         | Choice                                                                                                | Notes                                                                                                                   |
| ------------- | ----------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Frontend      | Next.js 16 (App Router) + TypeScript + Tailwind v4                                                    | Deployed to Vercel                                                                                                      |
| Backend       | **Convex** (TypeScript queries/mutations/actions)                                                     | Hosted database *and* function runtime in one. Replaced FastAPI + PostgreSQL on 2026-08-03 (see §1.1)                    |
| Database      | **Convex** documents                                                                                  | Same service as the backend; no separate DB to provision, no migrations to run                                          |
| Vector search | *Not implemented*                                                                                     | pgvector was enabled but never used (no vector column, no embeddings). Convex has its own vector indexes if picked up    |
| ML            | scikit-learn TF-IDF + Logistic Regression, **exported to JSON and evaluated in TypeScript**            | Trained offline in `ml/`; `ml/export_model_json.py` emits the weights and `convex/ai/classifier/` reproduces inference   |
| LLM layer     | Google Gemini **or** Groq (OpenAI-compatible), chosen via `LLM_PROVIDER`; schema-constrained JSON only | Explanation wording, follow-up phrasing, and hazard/category tagging ONLY — never the risk decision. Both sit behind the single `convex/ai/llm/client.ts` boundary and every reply is Zod-validated before use, so the configured provider cannot affect a risk decision |
| File storage  | *Not implemented*                                                                                     | Photo upload was specified but never built. Convex file storage if picked up                                            |
| Auth          | **Clerk** (single `user` role — no professional/admin roles)                                          | Session cookie, verified by Convex via a JWT template; route protection in `apps/frontend/proxy.ts`                      |
| Deployment    | Frontend → Vercel; backend + database → Convex; auth → Clerk                                          | Three managed services, nothing self-hosted                                                                             |

### 1.1 Why this changed (2026-08-03)

The original stack was Next.js → FastAPI → PostgreSQL, with the deliberate
rationale that "Python is chosen so the ML pipeline lives in the same
language/runtime as the API — no cross-language model-serving layer." That
reasoning was sound and is worth recording rather than quietly overwriting.

It was reversed for one requirement: **nothing may run on a self-hosted server.**
Convex executes TypeScript only, so keeping Python would have meant deploying and
paying for a fourth service purely to host the AI pipeline.

The obstacle was that `final_risk = max(ML, rules)` is non-negotiable (rules.md
§4.2), so the classifier could not simply be dropped — and it is not dead weight:
after the `user_skill` confound was fixed and the model retrained (2026-08-02),
test-split `max(ML, rules)` high-risk recall rose 0.686 → 0.743.

The resolution is that the shipped model is only numbers. TF-IDF is a vocabulary,
a set of IDF weights and a normalisation; logistic regression is a matrix multiply
and a softmax. Both port to TypeScript **exactly**, and both were verified to do
so before the Python was deleted:

- **Rule engine** — 2,316 evaluations (579 tasks x 4 answer states) produce
  identical risk levels, triggered rules, explanations and follow-ups.
  (`tools/compare_rule_engines.mjs`)
- **Classifier** — 579 rows produce identical predicted classes with a maximum
  probability difference of 1.55e-15, i.e. floating-point noise.
  (`tools/compare_classifiers.mjs`)

Both run in CI against committed Python outputs, so a future regression fails the
build rather than quietly changing what the product tells people is safe.

The catalog itself was not retyped: `tools/generate_catalog_ts.py` generated the
TypeScript from the Python source, because a dropped keyword or a floor typed as
3 instead of 4 compiles, runs, looks fine on review, and silently under-escalates
one hazard family forever.

## 2. High-Level App Flow

```
User (browser)
   │
   ▼
Next.js Frontend (Vercel)                    Clerk
   │  chat interface,          ◄────────────  session cookie, Google OAuth
   │  inline risk cards        proxy.ts guards /chat and /dashboard
   │
   │  useQuery / useMutation / useAction  (Clerk JWT attached automatically)
   ▼
Convex  (database + functions, one service)
   │
   ├── users.ts            JIT user creation from the Clerk identity
   ├── jobs.ts             create, list, follow-ups, delete
   ├── chat.ts             transcript
   ├── assessments.ts      the risk pipeline
   ├── recommendations.ts  tools / materials / PPE (placeholder)
   └── http.ts             Clerk webhook (user.updated / user.deleted)
              │
              ▼
      AI Decision Layer  (convex/ai/, TypeScript)
      ┌───────────────────────────────────────────┐
      │ ML Classifier  ──────┐                    │
      │  TF-IDF + LogReg     ├─► max() ──► finalRisk
      │  weights in JSON     │                    │
      │ Rule Engine       ────┘                   │
      │  ├─ hardcoded catalog (34 rules, floors,  │
      │  │  escalation logic — code-reviewed,     │
      │  │  never runtime-editable)               │
      │  └─ LLM hazard tagger: selects which      │
      │     hardcoded rules match the task text,  │
      │     quoting the user's own words as       │
      │     evidence — never assigns a risk       │
      │     number itself (rules.md §4.1)         │
      └───────────────────────────────────────────┘
              │
              ▼
      LLM Layer (convex/ai/llm/client.ts — actions only)
      Gemini or Groq: follow-up wording, hazard/category tagging
              │
              ▼
      Convex documents
      users, jobs, riskAssessments, chatMessages, aiLogs
```

Network I/O is only legal inside a Convex **action**, so a query or mutation
physically cannot reach a model. The rule arithmetic lives in pure functions and
mutations, which is what makes "the LLM never decides risk" a property of the
runtime rather than a convention held up by a docstring.

**Non-negotiable flow rule:** the frontend never calls the LLM directly, and the backend never returns a risk level that didn't pass through `max(ML, rules)`. The LLM only ever formats output the rule engine/classifier already decided, or tags which hardcoded hazard rule(s) apply — it never invents a rule or a risk number. There is no admin dashboard and no runtime-editable rule table; the hardcoded rubric lives in code (`apps/frontend/convex/ai/ruleEngine/`), authored with LLM assistance offline and reviewed like any other PR.

## 3. Repository Structure

Monorepo, two apps:

```
canidiy/
├── apps/
│   ├── frontend/                   # Next.js frontend
│   │   ├── src/
│   │   │   ├── (auth)/login/
│   │   │   ├── (auth)/register/
│   │   │   ├── chat/               # conversational task intake, follow-ups, inline risk cards
│   │   │   └── dashboard/          # user dashboard (history, saved)
│   │   ├── components/
│   │   │   ├── ui/                 # buttons, cards, form fields
│   │   │   ├── chat/               # MessageBubble, Composer, TypingIndicator, Sidebar
│   │   │   └── risk/               # RiskCard, RiskChip, HazardTag (rendered inline in chat)
│   │   ├── lib/                    # api client, auth helpers, types
│   │   └── styles/
│   │
│   │   ├── lib/                    # convexApi adapter, types, chat helpers
│   │   ├── proxy.ts                # route protection (Next 16 renamed middleware -> proxy)
│   │   └── convex/                 # THE BACKEND — database schema + all server functions
│   │       ├── schema.ts           # 5 tables: users, jobs, riskAssessments, aiLogs, chatMessages
│   │       ├── auth.config.ts      # Clerk as the identity provider
│   │       ├── http.ts             # Clerk webhook endpoint (.convex.site/clerk-webhook)
│   │       ├── users.ts            # JIT user creation, cascade delete
│   │       ├── jobs.ts             # create / list / follow-ups / delete
│   │       ├── chat.ts             # transcript
│   │       ├── assessments.ts      # max(ML, rules), aiLogs, fail-loud path
│   │       ├── recommendations.ts  # tools/materials/PPE (placeholder)
│   │       └── ai/
│   │           ├── jobLogic.ts     # shared pure logic (the follow-up gate AND scorer)
│   │           ├── ruleEngine/
│   │           │   ├── catalog.ts  # GENERATED from the Python original — do not hand-edit
│   │           │   ├── rules.ts    # evaluate / explain / follow-ups
│   │           │   ├── llmAssist.ts# hazard tagging + evidence grounding
│   │           │   └── ruleEngine.test.ts
│   │           ├── classifier/
│   │           │   ├── model.json  # exported TF-IDF + LogReg weights
│   │           │   ├── tfidf.ts    # sklearn-identical vectorizer
│   │           │   └── classify.ts # matrix multiply + softmax, fail-loud
│   │           └── llm/client.ts   # the ONLY module that calls an LLM
│
├── ml/                             # offline training + evaluation (not served)
│   ├── data/                       # labeled dataset (raw + processed)
│   ├── train_baseline.py           # TF-IDF + Logistic Regression  <- the shipped model
│   ├── train_embedding_model.py    # sentence-transformer + classifier (rejected, kept)
│   ├── export_model_json.py        # emits convex/ai/classifier/model.json
│   └── eval/                       # metrics, confusion matrix, reports
│
├── tools/                          # one-off porting + verification harnesses
│   ├── generate_catalog_ts.py      # Python catalog -> TypeScript catalog
│   ├── compare_rule_engines.mjs    # equivalence gate (CI)
│   ├── compare_classifiers.mjs     # equivalence gate (CI)
│   └── *_python_results.json       # frozen Python outputs the gates diff against
│
├── prd.md, architecture.md, rules.md, srs.md, phases.md, design.md, memory.md
│
└── infra/                          # no infrastructure; README documents env vars
```

> The docs live at the repository root rather than in `docs/`, contrary to the
> original plan above. Left as-is deliberately: every cross-reference in every
> file already points at the root paths.

## 4. Data Flow for a Single Assessment

1. `jobs.create` (action) — the LLM tags a category and which hardcoded hazard
   rules apply, quoting the user's own words as evidence for each. Tags are
   resolved ONCE here and persisted, so the hazard set that decides what the
   user is *asked* can never differ from the one that decides how the task is
   *scored*.
2. The catalog derives which safety-critical follow-ups are required from the
   hazards that fired, and `jobs.ts` stores the next unanswered one with
   LLM-phrased wording.
3. `jobs.submitFollowup` (action) — user answers; repeat until nothing is
   unresolved. An explicit "no" is an ANSWER and must not be re-asked; only an
   absent key counts as missing.
4. `assessments.assess` (action):
   - `ai/classifier` predicts risk + confidence from the description and category.
   - `ai/ruleEngine` independently evaluates the job against the hardcoded
     catalog. LLM-proposed rule ids are filtered against the catalog and then
     held to the same excludes / categories / gates as a keyword match, so a
     hallucinated or out-of-scope tag is discarded.
   - `finalRisk = max(mlRisk, ruleRisk)`.
   - The explanation is templated from the triggered rules — and must not cite
     the classifier when the classifier had no vote.
   - `recommendations` produces a tool/material/PPE list (placeholder).
   - An `aiLogs` row is written on EVERY attempt, including failures, with no
     sampling. A pipeline exception writes `status: "failed"` and blocks the DIY
     recommendation rather than falling back to anything that looks safe.
5. The frontend renders the card from `assessments.get`, which derives
   `safetyNotes` from the catalog at read time rather than storing a second copy
   of safety text that could drift. If risk ≥ Professional Recommended, the card
   recommends hiring a licensed professional — there is no in-app quote request
   or professional matching; that happens outside the product.

## 5. Database (summary — see SRS for full schema)

`users`, `task_categories`, `jobs`, `job_photos`, `risk_assessments`, `tools`, `materials`, `job_tool_recommendations`, `job_material_recommendations`, `ai_logs`.

Note: there is no `safety_rules` table. The hazard rule set is hardcoded in `ai/rule_engine/` (version-controlled, code-reviewed, LLM-assisted authoring) rather than admin-editable at runtime — `ai_logs` still records which rule IDs fired per assessment for audit purposes, it just reads from code constants instead of a DB row.
