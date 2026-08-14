# Software Requirements Specification — CanIDIY

A Risk-Aware Construction Task Assessment and Tool Recommendation Platform

Version 1.0 | Prepared for: Final Year Project Supervisor | Status: Draft
Conforms to IEEE 830-style SRS structure

> **Note:** This SRS reflects the original project scope and requirements. Where §10 (Technology Stack) lists options that were still open at the time (e.g. "FastAPI or Node.js/NestJS"), `architecture.md` has since finalized them — treat `architecture.md` as the source of truth for the tech stack in use. **The stack changed materially on 2026-08-03**: the backend and database moved to Convex and auth moved to Clerk, so there is no longer a separate API service, no PostgreSQL, and no JWT session of our own. §10 below has been updated; `architecture.md` §1.1 records why. Scope has also since narrowed: the admin dashboard and professional/vendor accounts described in earlier drafts were cut (see `prd.md` §4, `phases.md` renumbering notes); this revision reflects that cut throughout.

## 1. Introduction

### 1.1 Purpose

This Software Requirements Specification (SRS) defines the functional and non-functional requirements, system interfaces, data model, and constraints for CanIDIY, a web platform that assesses the safety risk of user-submitted DIY/construction tasks and recommends tools and materials, escalating unsafe tasks toward hiring a qualified professional as guidance rather than an in-app booking or quote flow. It is intended for the development team, project supervisor, and evaluation panel.

### 1.2 Scope

CanIDIY will be delivered as a deployed web platform with two principal subsystems: (1) a user-facing conversational task-intake, risk-report, and assessment-history interface, and (2) a hybrid AI risk-classification and recommendation engine. The system classifies tasks into one of five risk levels, explains the classification, and recommends tools/materials/PPE with cost and time estimates; for high-risk tasks it recommends hiring a licensed professional as guidance only — there is no in-app quote-request, professional accounts, or admin dashboard (see §1.5). Payment processing, certified legal permit verification, and computer-vision structural diagnosis are explicitly excluded from this version.

### 1.3 Definitions, Acronyms, and Abbreviations

| Term | Definition |
|---|---|
| DIY | Do-It-Yourself — a task performed by a non-professional user |
| PPE | Personal Protective Equipment |
| FR | Functional Requirement |
| NFR | Non-Functional Requirement |
| ML | Machine Learning |
| LLM | Large Language Model |
| Risk Level | One of five system-assigned categories: Safe DIY, DIY with Supervision, Professional Recommended, Professional Required, Dangerous/Do Not Attempt |
| Rule Engine | Deterministic component that enforces safety-critical overrides independent of the ML model |

### 1.4 References

- CanIDIY Final Year Project Proposal (source document for this SRS)
- OSHA Construction Focus Four Training — https://www.osha.gov/training/outreach/construction/focus-four
- OSHA Construction Focus Four: Electrocution Hazards — https://www.osha.gov/sites/default/files/electr_ig.pdf

### 1.5 Out of Scope

- Payment processing or contractor escrow
- Legally certified permit verification for any specific city or jurisdiction
- Computer-vision structural diagnosis from photographs
- Real-time contractor location tracking
- Any guarantee of professional work quality or legal/code compliance
- Admin dashboard or any runtime-editable safety rules — the rule set is hardcoded in `ai/rule_engine/`, changed via code review and redeploy, never via a live admin UI (see §2.5, `rules.md` §4)
- Professionals as app users — no professional accounts, dashboard, leads, or quote-routing/marketplace; the product's job ends at recommending the user hire a professional

## 2. Overall Description

### 2.1 Product Perspective

CanIDIY is a new, standalone product. It is not an extension of an existing platform. It integrates a frontend web application, a backend function layer, a hybrid AI decision layer, and a document database. (Originally specified with a PostgreSQL database plus pgvector for semantic retrieval and object storage for task photos; as built, persistence is Convex, and neither semantic retrieval nor photo upload was implemented — see §10.)

### 2.2 Product Functions (Summary)

- Account creation and authentication (single `user` role — no professional or admin roles)
- Natural-language task submission with structured metadata
- Dynamic follow-up questioning to close safety-relevant information gaps
- Five-level risk classification via a hybrid ML + rule-engine pipeline
- Human-readable, factor-based explanation of every classification
- Tool, material, and PPE recommendation with cost/time/difficulty estimates
- Professional-category recommendation as guidance only (no quote-routing or professional accounts)
- User dashboard: assessment history and saved recommendations

### 2.3 User Classes and Characteristics

| User Class | Technical Skill | Primary Use |
|---|---|---|
| End User (homeowner/tenant) | Low — no construction/electrical expertise assumed | Submit tasks, read risk reports, view assessment history |

### 2.4 Operating Environment

Modern desktop and mobile web browsers over HTTPS. As built: the frontend is deployed to Vercel and the backend functions and database are hosted by Convex, which is the system of record. Nothing is self-hosted and there is no container to operate. See §10.

### 2.5 Design and Implementation Constraints

- The final risk decision must never be determined by the ML/LLM component alone — the rule engine can only escalate risk, never lower it below the ML prediction (`final_risk = max(ML risk, rule risk)`)
- All safety rules are hardcoded in the rule engine (`ai/rule_engine/`), version-controlled and code-reviewed — never admin-editable or LLM-editable at runtime; there is no `admin` role and no runtime-editable rules table by design (see `rules.md` §4, `architecture.md` §5)
- Every risk classification must carry a machine-readable explanation (triggered rules and/or top model features), not free-text only

### 2.6 Assumptions and Dependencies

- Users describe their task honestly; the system has no independent means of verification. **Self-reported skill level is no longer collected** (2026-08-02) — precisely because it could not be verified and had stopped affecting any outcome (see FR-02, §8)
- A labeled dataset of sufficient size and quality (see §7.3) can be produced within the project timeline

## 3. System Features — Use Case Overview

| Use Case | Primary Actor | Trigger | Outcome |
|---|---|---|---|
| Submit Task | End User | User describes a DIY/construction task | Task record created; follow-up flow begins |
| Answer Follow-Up Questions | End User | System detects missing safety-relevant info | Task context completed for classification |
| Classify Risk | System (AI Engine) | Task context is complete | Risk level, confidence, hazard tags, explanation produced |
| View Risk Report | End User | Classification complete | User sees risk level, explanation, recommendations |
| View Assessment History | End User | User opens their dashboard | Prior task assessments and saved recommendations displayed |

## 4. Functional Requirements

| ID | Title | Requirement | Priority |
|---|---|---|---|
| FR-01 | User Registration and Login | The system shall allow users to register and log in under a single `user` role (no professional or admin roles exist). | High |
| FR-02 | Task Submission | The system shall allow a user to submit a task with description, category, and optional photo. **Skill level is no longer collected** (2026-08-02) and **urgency is no longer collected** (2026-07-31): nothing consumed it — it is excluded from the risk classifier as a non-safety feature and the rule engine ignores it — so asking cost the user a step in a safety flow and bought nothing. Both are for the same reason: nothing consumed them, so asking cost the user a step in a safety flow and bought nothing. Skill level specifically had become a *proxy for the label* — 91% of `Experienced` training rows were level 4, so the classifier returned 4 for an experienced user changing a light bulb and 1 for a beginner rewiring a consumer unit (`ml/analyze_skill_bias.py`). After the data was rebalanced it became the weakest feature in the model and the prediction was identical across all three values. The API still accepts both as optional and both columns are retained (nullable) so existing clients and rows are unaffected. Location and budget were never implemented. | High |
| FR-03 | Follow-Up Questions | The system shall generate follow-up questions specific to the task category and any risk factors not yet resolved (e.g., power isolation, load-bearing status). | High |
| FR-04 | Risk Classification | The system shall classify each completed task into exactly one of five risk levels: Safe DIY, DIY with Supervision, Professional Recommended, Professional Required, Dangerous/Do Not Attempt. | High |
| FR-05 | Risk Explanation | The system shall generate an explanation for every classification, listing the triggered safety factors and/or model rationale. | High |
| FR-06 | Tool and Material Recommendation | The system shall recommend required and optional tools, materials, and PPE for the submitted task. | High |
| FR-07 | Cost and Time Estimation | The system shall provide an estimated cost range, time range, and difficulty level for the task. | Medium |
| FR-08 | Professional Recommendation | The system shall recommend an appropriate professional category as guidance when the risk level is Professional Recommended or higher; this is informational only — there is no in-app quote request, professional accounts, or matching. | High |
| FR-09 | Assessment History | The system shall allow a user to view their previous task assessments and saved recommendations. | Medium |

### 4.1 Detailed Requirement: FR-04 Risk Classification

**Preconditions:** task description and all safety-critical follow-up answers are present.

**Main flow:** the ML classifier produces a predicted risk level and confidence score from task text and context; the rule engine independently evaluates the same context against its rule set; the system sets `final_risk = max(ML-predicted risk, rule-engine risk)` on the five-level ordinal scale.

**Postconditions:** a `risk_assessments` record is created containing risk level, confidence, hazard tags, and the list of triggered rules (if any).

**Exception flow:** if required context is missing and cannot be resolved through follow-up questions, the system shall default to the higher of the two most severe plausible risk levels rather than assume safety.

## 5. External Interface Requirements

### 5.1 User Interfaces

- Responsive web UI covering: conversational task intake, follow-up question flow, inline risk assessment card, tool/material/PPE recommendations, and an assessment history / saved-recommendations dashboard — a single user-facing app; there is no professional or admin dashboard

### 5.2 Software Interfaces

- REST API between frontend and backend for all task, assessment, and recommendation operations
- Database interface (Convex documents) for all persistent storage
- Vector similarity interface for semantic tool/material/task retrieval — **specified but not implemented**; no embeddings are computed or stored
- Object storage interface for task photo upload and retrieval
- LLM API interface used only for templated explanation wording and follow-up question phrasing, never for the final risk decision

### 5.3 Communications Interfaces

All client-server communication over HTTPS. Authentication is delegated to Clerk: the browser holds a Clerk session cookie, and Convex verifies a Clerk-issued JWT on every call via the `convex` JWT template. The application no longer signs, stores or revokes tokens of its own — which also retires the documented weakness of the previous scheme, a long-lived token held in `localStorage` with no revocation list.

## 6. Data Requirements

### 6.1 Core Entities

| Entity | Purpose | Key Attributes |
|---|---|---|
| users | Registered users — single role, no admin/professional roles | id, clerkUserId, name, email. **Credentials are not stored** — Clerk owns them |
| task_categories | Task category taxonomy | id, name (electrical, plumbing, carpentry, …) |
| jobs | User-submitted task and its context | id, userId, description, category, followupAnswers, llmHazardIds, status. `skill_level`, `urgency` and `budget` were retired from the product and are not stored |
| job_photos | Uploaded task images | id, job_id, url, caption |
| risk_assessments | Output of the classification engine | id, job_id, risk_level, confidence, explanation, hazard_tags, cost, time, difficulty |
| tools / materials | Catalog of recommendable items | id, name, category, price_range, ppe_flag |
| job_tool_recommendations / job_material_recommendations | Link jobs to recommended items | job_id, item_id, required/optional |
| ai_logs | Auditability of AI inputs/outputs | id, job_id, model_input, model_output, triggered_rules, timestamp |

Note: there is no `safety_rules` table. The hazard rule set is hardcoded in `ai/rule_engine/` (version-controlled, code-reviewed, LLM-assisted authoring) rather than admin-editable at runtime — `ai_logs` still records which rule IDs fired per assessment for audit purposes, it just reads from code constants instead of a DB row (see §2.5, `architecture.md` §5).

### 6.2 Data Retention and Auditability

Every risk assessment shall retain the model input, model output, confidence, and any rules triggered in `ai_logs`, so that a disputed classification can be reconstructed and reviewed by the engineering team.

## 7. Non-Functional Requirements

### 7.1 Safety and Reliability

- **NFR-01:** The final risk decision shall never depend solely on an unconstrained LLM response.
- **NFR-02:** When safety-critical information is missing, the system shall escalate risk rather than assume safety.
- **NFR-03:** The rule engine shall only ever raise, never lower, the ML-predicted risk level for a given task.

### 7.2 Evaluation Targets

| Metric | Description | Priority |
|---|---|---|
| Recall on high-risk classes | Proportion of Professional-Required/Dangerous tasks correctly identified as such | Primary metric — prioritized above overall accuracy |
| Macro F1-score | Balanced performance across all five risk classes | Secondary |
| Precision@5 (tool recommendation) | Relevance of top 5 recommended tools/materials | Secondary |
| Rule trigger correctness | % of safety test cases where the correct rule fires | Primary for safety validation |
| Expert review score | Domain expert (electrician/plumber/mason) rating of assessment correctness | Qualitative validation |

### 7.3 Explainability

Every risk classification shall include the specific triggered safety factors or rules, not a generic risk label alone.

### 7.4 Security

- Authentication required for all non-public endpoints
- Single `user` role — no elevated admin/professional access tiers exist in this product
- Input validation on all task submission and follow-up fields
- Secure, access-controlled storage for uploaded task images

### 7.5 Performance

Risk assessment results shall be returned within a response time acceptable for live demonstration and normal interactive use (target: a few seconds under typical load); the specific numeric SLA should be finalized once the ML/LLM latency is benchmarked.

### 7.6 Maintainability

Task categories and catalog data (tools, materials) may be extended via standard code changes and migrations. Safety rules are intentionally **not** runtime-editable — they live in `ai/rule_engine/` and change only via code review and redeploy (see §2.5, `rules.md` §4); there is no admin UI for this by design.

### 7.7 Scalability

The database and backend shall support adding new task categories and cities without schema-breaking changes.

### 7.8 Usability

A non-expert user shall be able to submit a task and receive a risk report without needing to understand ML/technical terminology; risk levels and explanations shall use plain language.

## 8. System Architecture Overview

The system follows a modular, layered architecture: a frontend web application; a backend API layer; an AI decision layer combining a supervised ML classifier with a deterministic safety rule engine; a recommendation layer for tools/materials; and a document data layer (Convex). The natural-language interface is a thin layer over this pipeline — it is not itself the source of the risk decision.

### 8.1 Hybrid Risk Decision Logic

```
final_risk = max( ML-predicted risk level, rule-engine risk level )
```

The ML classifier operates on task text and category. Available tools/PPE, urgency and user skill level are not inputs: the backend has no tools field, and urgency and skill level are no longer collected at all (see FR-02). The rule engine evaluates the same context against hardcoded safety-critical conditions (e.g., work on fixed wiring, gas connections, unknown load-bearing status, water near live electrical outlets) and can only escalate the final result upward on the five-level ordinal scale.

## 9. Safety Rule Catalog (Representative Set)

| Rule Condition | Resulting Escalation |
|---|---|
| Work on fixed wiring (any user) | Minimum risk becomes Professional Recommended |
| Main electrical panel, live wiring, or unknown power isolation | Professional Required or Dangerous/Do Not Attempt |
| Gas pipe, gas leak, or gas appliance connection | Professional Required or Dangerous/Do Not Attempt |
| Wall demolition with unknown load-bearing status | Professional Required; structural assessment recommended |
| Roof work or height above safe threshold | Professional Recommended or Professional Required |
| Water leak near an electrical outlet | Dangerous/Do Not Attempt; instruct isolating power first |

Note: this is a representative starting set. The full rule catalog is hardcoded in `ai/rule_engine/` — not admin-managed or runtime-editable (see §2.5) — and is expected to grow via code changes as the dataset and expert review process (§§6.2, 7.2) surface new hazard patterns.

## 10. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | Next.js / React, Tailwind CSS | Conversational task-intake UI and assessment-history dashboard |
| Backend | **Convex** (TypeScript functions) | Queries/mutations/actions for jobs, assessments, users, chat. No REST layer — the client calls functions directly |
| Database | **Convex** documents | Storage for all core entities; same service as the backend |
| Vector Search | *Not implemented* | Semantic retrieval was specified but never built |
| ML Models | TF-IDF + Logistic Regression (the shipped model) | Risk classification. Trained offline in `ml/`, exported to JSON and evaluated in TypeScript so it runs inside Convex. The sentence-embedding alternative was built, compared and rejected (Phase 4) |
| LLM Layer | Controlled prompting with templates | Explanation and follow-up question wording only |
| Storage | *Not implemented* | Task image upload was specified but never built |
| Auth | **Clerk** | Email+password and Google sign-in, rendered in this app's own UI via Clerk's headless hooks |
| Deployment | **Vercel + Convex + Clerk** | Three managed services; nothing self-hosted |

## 11. Acceptance Criteria for MVP Sign-Off

- System correctly classifies each of the four demo scenarios in the proposal (Safe DIY, Professional Recommended, Professional Required, Dangerous/Do Not Attempt) with a matching explanation.
- A safety-critical rule (e.g., gas line, live panel) escalates risk even when the ML model alone would predict a lower level.
- A user can view their assessment history and saved recommendations after completing one or more assessments.
- Trained classifier achieves the agreed-upon recall target on high-risk classes on a held-out test set (target to be finalized with supervisor, see PRD §10).
- All FR-01 through FR-09 requirements are implemented and demonstrable.

## 12. Appendix — Example Data Record

Example labeled dataset record used to train and evaluate the risk classifier:

```json
{
  "task_text": "install a ceiling fan in my bedroom",
  "category": "electrical",
  "user_skill": "beginner",
  "tools_available": ["screwdriver", "ladder"],
  "hazards": ["electrical_shock", "fall_from_height"],
  "risk_label": "professional_recommended",
  "professional_category": "electrician",
  "required_ppe": ["insulated_gloves", "safety_glasses"]
}
```
