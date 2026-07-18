# Software Requirements Specification — BuildSafe AI

A Risk-Aware Construction Task Assessment and Tool Recommendation Platform

Version 1.0 | Prepared for: Final Year Project Supervisor | Status: Draft
Conforms to IEEE 830-style SRS structure

> **Note:** This SRS reflects the original project scope and requirements. Where §10 (Technology Stack) lists options still open at the time (e.g., "FastAPI or Node.js/NestJS"), `architecture.md` has since finalized those decisions — treat `architecture.md` as the source of truth for the actual tech stack in use.

## 1. Introduction

### 1.1 Purpose

This Software Requirements Specification (SRS) defines the functional and non-functional requirements, system interfaces, data model, and constraints for BuildSafe AI, a web platform that assesses the safety risk of user-submitted DIY/construction tasks, recommends tools and materials, and escalates unsafe tasks to qualified professionals. It is intended for the development team, project supervisor, and evaluation panel.

### 1.2 Scope

BuildSafe AI will be delivered as a deployed web platform with three principal subsystems: (1) a user-facing task submission and risk-report interface, (2) a hybrid AI risk-classification and recommendation engine, and (3) an admin/professional management dashboard. The system classifies tasks into one of five risk levels, explains the classification, recommends tools/materials/PPE with cost and time estimates, and routes high-risk tasks toward a professional quote-request workflow. Payment processing, certified legal permit verification, and computer-vision structural diagnosis are explicitly excluded from this version (see §1.5).

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
| Quote Request | A user-initiated request for a professional to provide a price/time estimate on a task |

### 1.4 References

- BuildSafe AI Final Year Project Proposal (source document for this SRS)
- OSHA Construction Focus Four Training — https://www.osha.gov/training/outreach/construction/focus-four
- OSHA Construction Focus Four: Electrocution Hazards — https://www.osha.gov/sites/default/files/electr_ig.pdf

### 1.5 Out of Scope

- Payment processing or contractor escrow
- Legally certified permit verification for any specific city or jurisdiction
- Computer-vision structural diagnosis from photographs
- Real-time contractor location tracking
- Any guarantee of professional work quality or legal/code compliance

## 2. Overall Description

### 2.1 Product Perspective

BuildSafe AI is a new, standalone product. It is not an extension of an existing platform. It integrates a frontend web application, a backend API, a hybrid AI decision layer, a PostgreSQL database (with pgvector for semantic retrieval), and file storage for task photos.

### 2.2 Product Functions (Summary)

- Account creation, authentication, and role-based access (user, professional, admin)
- Natural-language task submission with structured metadata
- Dynamic follow-up questioning to close safety-relevant information gaps
- Five-level risk classification via a hybrid ML + rule-engine pipeline
- Human-readable, factor-based explanation of every classification
- Tool, material, and PPE recommendation with cost/time/difficulty estimates
- Professional-category recommendation and quote-request routing
- Admin management of categories, safety rules, tools, materials, professionals, vendors, and audit logs

### 2.3 User Classes and Characteristics

| User Class | Technical Skill | Primary Use |
|---|---|---|
| End User (homeowner/tenant) | Low — no construction/electrical expertise assumed | Submit tasks, read risk reports, request quotes |
| Professional | Domain expert, low-to-moderate software skill | Review and respond to quote requests |
| Admin | Moderate software skill, platform owner/operator | Maintain rules, catalog data, and oversee logs |

### 2.4 Operating Environment

Modern desktop and mobile web browsers over HTTPS. Backend deployed as a containerized/managed service; PostgreSQL as the system of record; object storage for images. See §10 for the specific technology stack.

### 2.5 Design and Implementation Constraints

- The final risk decision must never be determined by the ML/LLM component alone — the rule engine can only escalate risk, never lower it below the ML prediction (`final_risk = max(ML risk, rule risk)`)
- All safety rules and catalog data (tools, materials, categories, professionals) must be editable by admins without a code deployment
- Every risk classification must carry a machine-readable explanation (triggered rules and/or top model features), not free-text only

### 2.6 Assumptions and Dependencies

- Users self-report skill level and task details honestly; the system has no independent means of verification
- A labeled dataset of sufficient size and quality (see §7.3) can be produced within the project timeline
- Professional/vendor records in the MVP are admin-entered and are not independently, legally verified

## 3. System Features — Use Case Overview

| Use Case | Primary Actor | Trigger | Outcome |
|---|---|---|---|
| Submit Task | End User | User describes a DIY/construction task | Task record created; follow-up flow begins |
| Answer Follow-Up Questions | End User | System detects missing safety-relevant info | Task context completed for classification |
| Classify Risk | System (AI Engine) | Task context is complete | Risk level, confidence, hazard tags, explanation produced |
| View Risk Report | End User | Classification complete | User sees risk level, explanation, recommendations |
| Request Quote | End User | Task is Professional Recommended/Required/Dangerous | Quote request created and routed to professional category |
| Respond to Quote | Professional | New quote request assigned to category | Price/time estimate submitted to user |
| Manage Safety Rules | Admin | New hazard pattern identified | Rule created/edited/disabled, applied to future assessments |
| Manage Catalog | Admin | Tool/material/professional data changes | Catalog updated; reflected in future recommendations |
| Review AI Logs | Admin | Disputed or low-confidence classification | Admin inspects inputs, outputs, and triggered rules |

## 4. Functional Requirements

| ID | Title | Requirement | Priority |
|---|---|---|---|
| FR-01 | User Registration and Login | The system shall allow users to register, log in, and access a role-appropriate dashboard (user, professional, or admin). | High |
| FR-02 | Task Submission | The system shall allow a user to submit a task with description, category, location, skill level, budget, urgency, and optional photos. | High |
| FR-03 | Follow-Up Questions | The system shall generate follow-up questions specific to the task category and any risk factors not yet resolved (e.g., power isolation, load-bearing status). | High |
| FR-04 | Risk Classification | The system shall classify each completed task into exactly one of five risk levels: Safe DIY, DIY with Supervision, Professional Recommended, Professional Required, Dangerous/Do Not Attempt. | High |
| FR-05 | Risk Explanation | The system shall generate an explanation for every classification, listing the triggered safety factors and/or model rationale. | High |
| FR-06 | Tool and Material Recommendation | The system shall recommend required and optional tools, materials, and PPE for the submitted task. | High |
| FR-07 | Cost and Time Estimation | The system shall provide an estimated cost range, time range, and difficulty level for the task. | Medium |
| FR-08 | Professional Recommendation | The system shall recommend an appropriate professional category when the risk level is Professional Recommended or higher. | High |
| FR-09 | Quote Request | The system shall allow a user to create a quote request for a task classified as Professional Recommended or higher, and route it to matching professionals. | High |
| FR-10 | Admin Dashboard | The system shall provide admins CRUD access to task categories, safety rules, tools, materials, professionals, vendors, and audit logs. | High |
| FR-11 | Professional Dashboard | The system shall allow professionals to view quote requests assigned to their category and submit price/time estimates. | Medium |
| FR-12 | Assessment History | The system shall allow a user to view their previous task assessments and saved recommendations. | Medium |

### 4.1 Detailed Requirement: FR-04 Risk Classification

**Preconditions:** task description and all safety-critical follow-up answers are present.

**Main flow:** the ML classifier produces a predicted risk level and confidence score from task text and context; the rule engine independently evaluates the same context against its rule set; the system sets `final_risk = max(ML-predicted risk, rule-engine risk)` on the five-level ordinal scale.

**Postconditions:** a `risk_assessments` record is created containing risk level, confidence, hazard tags, and the list of triggered rules (if any).

**Exception flow:** if required context is missing and cannot be resolved through follow-up questions, the system shall default to the higher of the two most severe plausible risk levels rather than assume safety.

### 4.2 Detailed Requirement: FR-09 Quote Request

**Preconditions:** task risk level is Professional Recommended, Professional Required, or Dangerous/Do Not Attempt.

**Main flow:** user confirms intent to request a quote; system creates a `quote_requests` record linked to the job and the recommended `professional_category`; matching professionals are notified/listed.

**Postconditions:** professional(s) can view the request and submit a `quotes` record with price, time, message, and status.

**Exception flow:** if no professional exists for the required category, the system shall clearly inform the user rather than silently failing.

## 5. External Interface Requirements

### 5.1 User Interfaces

- Responsive web UI covering: task submission form, follow-up question flow, risk report view, saved-jobs/history view, quote-request flow (end user)
- Professional dashboard: assigned quote requests, estimate submission form
- Admin dashboard: CRUD screens for categories, rules, tools, materials, professionals, vendors; read-only AI log viewer

### 5.2 Software Interfaces

- REST API between frontend and backend for all task, assessment, recommendation, admin, and quote operations
- Database interface (PostgreSQL) for all persistent storage
- Vector similarity interface (pgvector or equivalent) for semantic tool/material/task retrieval
- Object storage interface for task photo upload and retrieval
- LLM API interface used only for templated explanation wording and follow-up question phrasing, never for the final risk decision

### 5.3 Communications Interfaces

All client-server communication over HTTPS. Authentication via token-based session (e.g., JWT) attached to API requests.

## 6. Data Requirements

### 6.1 Core Entities

| Entity | Purpose | Key Attributes |
|---|---|---|
| users | Users, admins, professionals, vendors with role-based access | id, role, name, contact, credentials |
| task_categories | Task category taxonomy | id, name (electrical, plumbing, carpentry, …) |
| jobs | User-submitted task and its context | id, user_id, description, category_id, skill_level, urgency, budget |
| job_photos | Uploaded task images | id, job_id, url, caption |
| risk_assessments | Output of the classification engine | id, job_id, risk_level, confidence, explanation, hazard_tags, cost, time, difficulty |
| safety_rules | Rule engine conditions and escalation actions | id, condition, resulting_risk_level, active |
| tools / materials | Catalog of recommendable items | id, name, category, price_range, ppe_flag, vendor_id |
| job_tool_recommendations / job_material_recommendations | Link jobs to recommended items | job_id, item_id, required/optional |
| professional_categories / professionals | Professional taxonomy and profiles | id, category, verification_status, service_area, rating |
| quote_requests / quotes | Quote workflow | id, job_id, professional_id, price, time, status |
| ai_logs | Auditability of AI inputs/outputs | id, job_id, model_input, model_output, triggered_rules, timestamp |

### 6.2 Data Retention and Auditability

Every risk assessment shall retain the model input, model output, confidence, and any rules triggered in `ai_logs`, so that a disputed classification can be reconstructed and reviewed by an admin.

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
- Role-based access control enforced at the API layer (user / professional / admin)
- Input validation on all task submission and follow-up fields
- Secure, access-controlled storage for uploaded task images

### 7.5 Performance

Risk assessment results shall be returned within a response time acceptable for live demonstration and normal interactive use (target: a few seconds under typical load); the specific numeric SLA should be finalized once the ML/LLM latency is benchmarked.

### 7.6 Maintainability

Admins shall be able to add, edit, or disable task categories, safety rules, tools, materials, and professional categories without a code deployment.

### 7.7 Scalability

The database and backend shall support adding new task categories, cities, vendors, and professional categories without schema-breaking changes.

### 7.8 Usability

A non-expert user shall be able to submit a task and receive a risk report without needing to understand ML/technical terminology; risk levels and explanations shall use plain language.

## 8. System Architecture Overview

The system follows a modular, layered architecture: a frontend web application; a backend API layer; an AI decision layer combining a supervised ML classifier with a deterministic safety rule engine; a recommendation layer for tools/materials/professionals; a PostgreSQL data layer with vector-search support; and a quotation/marketplace layer connecting users to professionals. The natural-language interface is a thin layer over this pipeline — it is not itself the source of the risk decision.

### 8.1 Hybrid Risk Decision Logic

```
final_risk = max( ML-predicted risk level, rule-engine risk level )
```

The ML classifier operates on task text, category, user skill level, available tools/PPE, urgency, and follow-up answers. The rule engine evaluates the same context against admin-managed safety-critical conditions (e.g., electrical wiring + beginner user, gas connections, unknown load-bearing status, water near live electrical outlets) and can only escalate the final result upward on the five-level ordinal scale.

## 9. Safety Rule Catalog (Representative Set)

| Rule Condition | Resulting Escalation |
|---|---|
| Electrical wiring task + beginner user | Minimum risk becomes Professional Recommended |
| Main electrical panel, live wiring, or unknown power isolation | Professional Required or Dangerous/Do Not Attempt |
| Gas pipe, gas leak, or gas appliance connection | Professional Required or Dangerous/Do Not Attempt |
| Wall demolition with unknown load-bearing status | Professional Required; structural assessment recommended |
| Roof work or height above safe threshold | Professional Recommended or Professional Required |
| Water leak near an electrical outlet | Dangerous/Do Not Attempt; instruct isolating power first |

Note: this is a representative starting set. The full rule catalog is admin-managed and expected to grow as the dataset and expert review process (§§6.2, 7.2) surface new hazard patterns.

## 10. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | Next.js / React, Tailwind CSS | User, admin, and professional dashboards |
| Backend | FastAPI or Node.js/NestJS | REST APIs for jobs, assessments, users, rules, tools, professionals, quotes |
| Database | PostgreSQL | Structured storage for all core entities |
| Vector Search | pgvector / sentence embeddings | Semantic retrieval for similar tasks, tools, materials |
| ML Models | TF-IDF + Logistic Regression baseline; transformer/sentence-embedding classifier | Risk classification |
| LLM Layer | Controlled prompting with templates | Explanation and follow-up question wording only |
| Storage | Supabase Storage / Cloudinary | Task images and attachments |
| Deployment | Vercel + Render/Railway/Fly.io + managed Postgres | Deployable FYP demo environment |

## 11. Acceptance Criteria for MVP Sign-Off

- System correctly classifies each of the four demo scenarios in the proposal (Safe DIY, Professional Recommended, Professional Required, Dangerous/Do Not Attempt) with a matching explanation.
- A safety-critical rule (e.g., gas line, live panel) escalates risk even when the ML model alone would predict a lower level.
- Admin can add/edit a safety rule and see it take effect on the next assessment without a deployment.
- A Professional-Required or higher task can be taken end-to-end through quote request to a professional response.
- Trained classifier achieves the agreed-upon recall target on high-risk classes on a held-out test set (target to be finalized with supervisor, see PRD §10).
- All FR-01 through FR-12 requirements are implemented and demonstrable.

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
