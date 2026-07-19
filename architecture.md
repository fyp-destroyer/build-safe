# Architecture — BuildSafe AI

## 1. Tech Stack (decided)

| Layer         | Choice                                                                                                | Notes                                                                                                                   |
| ------------- | ----------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Frontend      | Next.js (App Router) + TypeScript + Tailwind CSS                                                      | SSR for dashboards, easy deploy to Vercel                                                                               |
| Backend       | FastAPI (Python)                                                                                      | Python chosen so the ML pipeline lives in the same language/runtime as the API — no cross-language model-serving layer |
| Database      | PostgreSQL                                                                                            | Relational core; pgvector extension enabled                                                                             |
| Vector search | pgvector + sentence-transformers embeddings                                                           | Semantic tool/material/task retrieval                                                                                   |
| ML            | scikit-learn (baseline: TF-IDF + Logistic Regression) → sentence-transformer + classifier (improved) | Both versions kept; compare in eval report                                                                              |
| LLM layer     | Google Gemini API, template-constrained + schema-constrained (structured JSON output) prompts         | Explanation wording, follow-up question phrasing, and hazard/category tagging ONLY — never the risk decision itself. Switched from Anthropic API to Gemini 2026-07-19 (see memory.md decisions log). |
| File storage  | Supabase Storage (or S3-compatible)                                                                   | Task photos                                                                                                             |
| Auth          | JWT-based session (single`user` role — no professional/admin roles)                                | Enforced at API middleware layer                                                                                        |
| Deployment    | Frontend → Vercel; Backend → Render/Railway/Fly.io; DB → managed Postgres (Supabase/Neon)          |                                                                                                                         |

> If the team prefers a single-language stack, Node.js/NestJS is an acceptable backend swap — but ML inference would then need to run as a separate Python microservice. Default to FastAPI unless the team has a strong reason to switch.

## 2. High-Level App Flow

```
User (browser)
   │
   ▼
Next.js Frontend  ──────────────►  FastAPI Backend
   │  (chat interface,                │
   │   inline risk cards,             ├── /auth        (login, register)
   │   dashboard)                     ├── /jobs         (submit task, follow-ups)
   │                                  ├── /assessments  (risk classification results)
   │                                  └── /recommendations (tools/materials/PPE)
   │                                       │
   │                                       ▼
   │                              AI Decision Layer
   │                              ┌───────────────────────────────────────────┐
   │                              │ ML Classifier  ──────┐                    │
   │                              │                      ├─► max() ──► final_risk
   │                              │ Rule Engine       ────┘                   │
   │                              │  ├─ hardcoded rubric (risk levels,        │
   │                              │  │  escalation logic — code-reviewed,    │
   │                              │  │  never runtime-editable)               │
   │                              │  └─ LLM hazard classifier: tags which    │
   │                              │     hardcoded hazard rules match the     │
   │                              │     task text — never assigns a risk     │
   │                              │     number itself (see rules.md §4.1)    │
   │                              └───────────────────────────────────────────┘
   │                                       │
   │                                       ▼
   │                              LLM Layer (templated)
   │                              explanation text, follow-up wording
   │                                       │
   ▼                                       ▼
Rendered chat + risk card       PostgreSQL (+ pgvector)
                                 users, jobs, risk_assessments,
                                 tools, materials, ai_logs
```

**Non-negotiable flow rule:** the frontend never calls the LLM directly, and the backend never returns a risk level that didn't pass through `max(ML, rules)`. The LLM only ever formats output the rule engine/classifier already decided, or tags which hardcoded hazard rule(s) apply — it never invents a rule or a risk number. There is no admin dashboard and no runtime-editable rule table; the hardcoded rubric lives in code (`ai/rule_engine/`), authored with LLM assistance offline and reviewed like any other PR.

## 3. Repository Structure

Monorepo, two apps:

```
buildsafe-ai/
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
│   └── backend/                    # FastAPI backend
│       ├── main.py
│       ├── routers/
│       │   ├── auth.py
│       │   ├── jobs.py
│       │   ├── assessments.py
│       │   └── recommendations.py
│       ├── ai/
│       │   ├── classifier/         # ML model load/predict
│       │   ├── rule_engine/        # hardcoded rubric + hazard rules (code, not DB), escalation logic
│       │   ├── explanation/        # LLM templating for explanations
│       │   └── recommend/          # tool/material/PPE recommendation logic
│       ├── models/                 # SQLAlchemy models (mirrors DB schema)
│       ├── schemas/                # Pydantic request/response schemas
│       ├── services/               # business logic, orchestrates ai/ + models/
│       ├── core/                   # config, security/auth, db session
│       └── tests/
│
├── ml/
│   ├── data/                       # labeled dataset (raw + processed), never committed with PII
│   ├── notebooks/                  # EDA, model comparison
│   ├── train_baseline.py           # TF-IDF + Logistic Regression
│   ├── train_embedding_model.py    # sentence-transformer + classifier
│   └── eval/                       # metrics, confusion matrix, reports
│
├── docs/
│   ├── prd.md
│   ├── architecture.md
│   ├── rules.md
│   ├── phases.md
│   ├── design.md
│   └── memory.md
│
└── infra/                          # deployment configs (Vercel, Render, migrations)
```

## 4. Data Flow for a Single Assessment

1. `POST /jobs` — creates a `jobs` row from the task submission.
2. Backend determines missing safety-critical fields → returns follow-up questions.
3. `PATCH /jobs/{id}/followup` — user answers; repeat until context is complete.
4. `POST /jobs/{id}/assess`:
   - `ai/classifier` predicts risk + confidence from job context.
   - `ai/rule_engine` independently evaluates job context against the hardcoded hazard rule set — an LLM call classifies which hardcoded rule(s) match the task text (hazard tagging only, never a risk number), then the hardcoded rubric maps matched hazards to an escalation floor.
   - Service layer computes `final_risk = max(classifier_risk, rule_risk)`.
   - `ai/explanation` generates templated explanation text (facts inserted, not invented).
   - `ai/recommend` produces tool/material/PPE list + cost/time estimate.
   - Everything is written to `risk_assessments` and `ai_logs`.
5. Frontend renders the risk report from `GET /assessments/{job_id}`. If risk ≥ Professional Recommended, the card recommends hiring a licensed professional — there is no in-app quote request or professional matching; that happens outside the product.

## 5. Database (summary — see SRS for full schema)

`users`, `task_categories`, `jobs`, `job_photos`, `risk_assessments`, `tools`, `materials`, `job_tool_recommendations`, `job_material_recommendations`, `ai_logs`.

Note: there is no `safety_rules` table. The hazard rule set is hardcoded in `ai/rule_engine/` (version-controlled, code-reviewed, LLM-assisted authoring) rather than admin-editable at runtime — `ai_logs` still records which rule IDs fired per assessment for audit purposes, it just reads from code constants instead of a DB row.
