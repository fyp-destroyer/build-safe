# Final Year Project Feasibility Report

**CanIDIY** *(proposal working title: BuildSafe AI / ConstructMate)*
A Risk-Aware Construction Task Assessment and Tool Recommendation Platform

| Field                   | Value                                                       |
| ----------------------- | ----------------------------------------------------------- |
| Degree Program          | BS Computer Science / Computer Science Final Year Project   |
| Project Type            | Product-Based FYP (AI/ML, Web Platform, Database)           |
| Team Size               | 3 Members                                                   |
| Submitted By            | Muhammad Sarim Khan Ghouri, Areeb ur Rehman, Syed Ammar Ali |
| Registration Numbers    | 23k0720, 23k0682, 23k0740                                   |
| Supervisor              | Zain ul Hassan                                              |
| Department / University | School of Computing, Fast NUCES                             |
|                         |                                                             |
|                         |                                                             |

---

## 1. Purpose of This Report

This report assesses whether CanIDIY can be completed as a Final Year Project within the time, skills, and resources available to a 3-member Computer Science team. Sections 3 to 7 follow the standard TELOS structure, covering technical, economic, legal, operational, and schedule feasibility in turn. Section 8 gives the overall recommendation. Unusually for a feasibility report, most of the assessment below rests on measured results from a partly built system rather than on projections, because implementation began before this document was written.

---

## 2. Project Summary

CanIDIY lets a non-expert user describe a DIY or small construction task in natural language and decides, before giving any how-to guidance, whether the task is safe to attempt at all. The system asks clarifying follow-up questions, classifies the task into one of five risk levels running from Safe DIY through to Dangerous / Do Not Attempt, explains the decision in plain language, and recommends the tools, materials, and PPE the task would require.

Its defining constraint is that the final risk level is never decided by a language model. Risk is computed as `finalRisk = max(ML classifier output, rule engine output)`, where the rule engine is a hardcoded, version-controlled catalog of hazard rules that can only escalate risk and never lower it. The LLM's role is limited to phrasing follow-up questions, generating explanation text from templates, and tagging which of the hardcoded hazard rules apply to a task's text. That separation is what makes the safety behaviour of the product auditable, and it shapes almost every feasibility judgement in this report.

---

## 3. Technical Feasibility

The frontend is Next.js 16 (App Router) with TypeScript and Tailwind v4, deployed on Vercel, and has been click-tested end to end in a real browser across all five risk tiers and the full authentication flow. The backend and database were originally FastAPI, SQLAlchemy, and Postgres with pgvector, and were migrated on 2026-08-03 to Convex, which holds both the database and all backend functions in TypeScript, in order to satisfy a requirement that nothing be self-hosted. That migration was not a rewrite by feel. The rule engine and classifier were ported and then verified row by row against the original Python implementation, matching on 2,316 of 2,316 rule evaluations and 579 of 579 classifier predictions to within 1.55e-15, with both comparisons re-run in CI against committed baselines so that the safety-critical logic cannot silently drift. Authentication uses Clerk driven through its headless hooks (`useSignIn` and `useSignUp`), which preserved the original hand-built UI design exactly while adding real route protection at the edge in `proxy.ts` instead of a client-side redirect.

**Planned change: reversion to FastAPI on Render.** The team intends to revert the backend and database to the original FastAPI, SQLAlchemy, and Postgres stack, hosted on Render's free tier. The main driver is that a Python service can load the machine learning model natively, which the TypeScript-only Convex runtime could not, and which in turn unlocks the model change described below. Two things make this reversion far cheaper than a normal migration. The FastAPI implementation is not lost; it exists in version control and can be restored rather than rewritten. More importantly, it is the implementation that the Convex port was proven equivalent to, so restoring it means returning to code whose safety-critical behaviour was already validated row by row, and the same comparison harnesses can be pointed back the other way to confirm nothing regressed in transit. The work is therefore best understood as restoring a verified baseline and re-hosting it, not as building a third backend from scratch. Because the reversion had not been carried out when this report was written, the verification claims above describe the Convex implementation currently running, and the report should be updated with re-run comparison figures once the reversion lands.

The machine learning component currently shipping is a TF-IDF model over word and character n-grams feeding a logistic regression classifier, trained on 555 labeled examples. A sentence-embedding alternative (`all-MiniLM-L6-v2` with logistic regression) was built and compared under paired 5-fold cross-validation specifically to justify the choice rather than assume it. The two proved statistically indistinguishable in accuracy, and since the embedding model would have added roughly 90 MB and a torch dependency to a serving path that could not host them, the simpler TF-IDF model shipped. That experiment is concrete evidence that the team can execute a controlled model-selection comparison rather than train a single model and stop.

**Planned change: permanent adoption of the sentence-embedding model.** With the move back to a Python service, the constraint that decided the original comparison no longer applies, and the team intends to make the embedding model the permanent classifier. It is important that the report states the justification accurately: the cross-validation result did not show the embedding model to be more accurate, so the case for switching rests on architectural fit and future headroom rather than on measured accuracy. Embeddings generalise better to task phrasings the training set never contained, which matters for a 555-example corpus, and having vectors available at runtime makes semantic retrieval over past assessments possible through pgvector, which is already part of the restored stack. Claiming an accuracy improvement the experiment did not find would be the one thing likely to damage this section under questioning, so the switch should be presented as reopening a decision whose constraints changed.

The rule engine itself contains 21 hardcoded hazard rules, each escalate-only, covered by 45 property tests including adversarial inputs such as hallucinated LLM-returned rule identifiers and SQL-injection-shaped strings, which together demonstrate that the LLM cannot introduce a rule outside the fixed catalog. It is unaffected by either planned change, which is the point of keeping risk decisions out of the model layer.

Four technical risks are worth surfacing rather than hiding:

- **Classifier recall on the severe classes.** Headline recall on the two most severe risk classes is 0.902 in deployment with rules and ML combined, rising to 1.000 on tasks whose hazard is stated explicitly in the task text. That 1.000 figure is measured on training-adjacent data and is deliberately never reported alone. It is corroborated by a held-out set of 24 tasks, 14 of them adversarial negatives, written and committed before the rules that would be tested against them, all 24 of which the system caught. This is the strongest evidence in the project that its recall claims are trustworthy rather than overfit. These figures were measured with the TF-IDF classifier and must be re-measured, on the same held-out set, once the embedding model becomes the shipped classifier.
- **Memory ceiling on the free hosting tier.** This is the most significant new risk the two planned changes create together. Render's free web service instances provide 512 MB of RAM, while sentence-transformers loaded on top of PyTorch commonly occupies a large fraction of that before the application code is counted, so the combination may not fit. The team should measure resident memory locally before committing to the plan. If it does not fit, the practical mitigations, in increasing order of cost, are to export the model to ONNX and serve it through onnxruntime with a tokenizer instead of the full torch stack, which typically cuts both install size and resident memory substantially, to precompute embeddings where the input space allows it, or to move to Render's paid starter instance. None of these is a blocker, but the choice should be made deliberately rather than discovered on deployment day.
- **Cold starts on the free tier.** Render spins free web services down after roughly 15 minutes of inactivity, and the next request pays a spin-up delay of about a minute. Loading an embedding model at startup adds to that delay. This is acceptable for an FYP demonstration but must be planned around: warm the service shortly before any live demonstration rather than opening it cold in front of an evaluator.
- **A local environment constraint.** Turbopack crashes on the primary development machine, so `npm run dev` runs with `--webpack` as a documented workaround. This is an inconvenience, not a blocker, and does not affect the deployed build.

Technical feasibility is therefore not a projection. It is a fact established by a working, tested, CI-gated system covering seven of nine phases. The two planned changes revisit decisions rather than introduce unknowns, and both restore code or models the team has already built and evaluated once.

---

## 4. Economic Feasibility

The economic question is whether the team can afford to build and demonstrate the system. The answer is that cost is small and bounded, consisting of a modest deliberate spend on LLM credits and a possible small monthly hosting charge, rather than being strictly zero.

Hosting sits on managed platforms with free tiers that cover FYP-scale traffic, meaning a handful of demonstration users rather than production load. Vercel serves the frontend and Clerk handles authentication, both comfortably within their free tiers. Under the planned reversion described in Section 3, the FastAPI backend and its Postgres database move to Render's free tier. Two characteristics of that tier belong in a feasibility report rather than being discovered during deployment week:

- **Free Postgres instances expire 30 days after creation.** After expiry the database is inaccessible unless upgraded to a paid instance, with a 14 day grace period before the data is deleted outright, and only one free database may be active per workspace. For a project with a fixed demonstration date this is a scheduling constraint as much as a financial one. The safe response is either to create the production database close to the demonstration window while keeping a seed script that can rebuild it from scratch, which Phase 8 requires for demo data in any case, or to budget for the paid instance across the final months.
- **Free web services provide 512 MB of RAM and 750 instance hours per workspace per month, and spin down after inactivity.** The instance hours are ample for a single service, but the memory ceiling interacts directly with the planned embedding model, as set out in Section 3.

Neither point makes the plan infeasible. Together they mean the honest hosting figure is not zero but a small optional monthly fee, on the order of one paid starter instance, should the memory ceiling or the database expiry force an upgrade. Naming that upgrade path and its rough magnitude is better than presenting free tiers as though they scale indefinitely, which invites precisely the question the report could not otherwise answer.

LLM usage remains inexpensive because of the safety architecture rather than in spite of it. The LLM layer, backed by either Gemini or Groq and selected through the `LLM_PROVIDER` setting, is used only for phrasing and tagging and never for risk decisions, so calls are short and infrequent, at most one per assessment. Although both providers offer free-tier keys adequate for development, the team plans to purchase a small amount of API credit so that rate limiting or quota exhaustion cannot disrupt development or, more importantly, a live demonstration. This is best characterised as an insurance purchase rather than a running cost, and it is bounded by the usage pattern just described: short prompts, one call per assessment, and a demonstration workload measured in tens of assessments rather than thousands. The system also degrades gracefully when no key is present, since category tagging falls back quietly rather than failing the whole assessment, so the credit buys smoothness rather than covering a single point of failure.

No paid tooling was required on the team side at any point, since scikit-learn, sentence-transformers, FastAPI, and the entire JavaScript and TypeScript toolchain are open source. Genuine production cost, were the system scaled beyond a student project, would be driven by user volume through hosting tier upgrades plus LLM API usage. That falls outside FYP feasibility but is worth acknowledging so the analysis does not read as if the current arrangement scales unchanged.

---

## 5. Legal and Ethical Feasibility

This is the section reviewers will scrutinise most closely, because the product gives safety-relevant advice to non-experts.

The liability posture is that CanIDIY is a decision-support tool, not a certified safety authority. Rule explanations are deliberately jurisdiction-neutral: they state the hazard and its consequence, for example "unresolved gas leak, evacuate, do not operate switches," rather than citing specific regulations or building codes. The project does not target a single regulatory jurisdiction and should not claim legal authority it cannot back. This was a conscious decision recorded in the Phase 5 log in `memory.md`, not an oversight.

Several safety-critical design constraints act as ethical risk mitigation and are worth stating explicitly in any submitted version of this report:

- The LLM never assigns a risk number. It can only select from a fixed, code-reviewed hazard catalog, and any hallucinated selection is discarded rather than silently accepted.
- Missing answers, and answers of "unsure," to safety-critical follow-up questions escalate risk to the worst plausible case instead of assuming safety.
- AI pipeline failures set the assessment status to `"failed"` and block the DIY recommendation outright. There is no silent fallback to a "safe" result.
- Every assessment attempt, including every failure, is logged to `aiLogs`, which supports an audit-trail argument if accountability is raised in defence.

On data privacy, user task descriptions, and in the original proposal's fuller scope optional photographs, are personal input data. The current implementation stores task text under Clerk-authenticated ownership scoping: every function begins with `requireUser` and scopes by owner, and a lookup of another user's row returns "not found" rather than "forbidden," so the existence of other users' records is never leaked. That guarantee is a property of the authorization model rather than of the database, so it carries across the planned reversion unchanged, but it is one of the specific behaviours the restored FastAPI endpoints should be re-tested for rather than assumed.

One caveat must be disclosed plainly rather than smoothed over. The dataset's high-risk labels were audited against 11 published safety standards, including HSE guidance, the OSHA Focus Four, the UK Gas Safety Regulations 1998, the Control of Asbestos Regulations 2012, BS 7671 and Part P, and the Confined Spaces Regulations 1997, reaching 100% conformance after fixes. That audit was performed by the team, however, and is not independent expert inter-rater agreement. The project's own documentation flags this throughout, and the report should do the same. The remedy, a licensed tradesperson labelling a blind sample so that Cohen's kappa can be computed, is a known follow-up item, realistically out of scope for the current timeline but worth naming as future work.

The project is therefore legally and ethically feasible as an academic demonstrator, provided the submission is explicit that CanIDIY augments professional judgement rather than replacing it. The product's core design principle, `finalRisk = max(ML, rules)` with an escalate-only rule engine, already embodies exactly that position.

---

## 6. Operational Feasibility

Operational feasibility asks two things: whether the intended users can actually use the system, and whether the team can operate and maintain it.

The target users identified in the original proposal are homeowners, tenants, and small property owners with no construction expertise. The interface was therefore designed as a conversation rather than a form, and its visual language was kept deliberately close to ChatGPT: a centred message thread, user turns distinguished from system turns, a persistent composer at the foot of the page, and a collapsible history sidebar. This resemblance is a design decision rather than an accident of convenience. Consumer chat assistants have become the reference interface for describing a problem in one's own words, so borrowing their conventions means a first-time user arrives already knowing how to operate the product and spends their attention on describing the task instead of learning the interface. The gain is largest precisely for the non-technical audience CanIDIY targets, who are the least likely to persevere through an unfamiliar layout. Quick-reply chips for follow-up questions extend the same principle, since they let a user answer a safety-critical question with one tap rather than composing a sentence, which both lowers effort and reduces the chance of an ambiguous answer that the system would have to treat as missing and escalate.

Usability has been validated rather than assumed: the full user journey of registering, submitting a task, answering follow-ups, receiving a risk card, and revisiting history was manually click-tested end to end in a real browser across all five risk tiers, against the real backend rather than scripted demo data, including session persistence across reload and restoration of history.

Maintainability was shaped by one significant trade-off. The safety rule catalog is intentionally not editable by an administrator at runtime, which is a cut from the original proposal's admin dashboard concept. A 3-person team cannot realistically build, secure, and test a full CRUD admin interface and simultaneously keep the safety guarantee airtight within an FYP timeline, so rule changes instead go through code review and redeployment. This should be framed as a decision that increases feasibility, since it shrinks the surface that must be built and tested, at a modest cost in runtime flexibility. The admin dashboard and the professional and vendor marketplace modules were formally cut from scope on 2026-07-18 for the same reason, pruned deliberately against the Must/Should/Could priority in `prd.md` rather than allowed to slip silently.

The system is therefore operationally feasible, and the scope decisions already taken are themselves evidence that the team is managing feasibility risk proactively, which is worth stating explicitly to a supervisor or evaluator.

---

## 7. Schedule Feasibility

The schedule question is whether the remaining work can realistically be finished in the time left. Current phase status is as follows:

| Phase                                       | Status                                                                                                                                                                                                                                                                                                                            |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0. Project Setup                            | Complete                                                                                                                                                                                                                                                                                                                          |
| 1. Research & Scope Finalization            | Complete (provisional; supervisor confirmation pending)                                                                                                                                                                                                                                                                           |
| 2. Dataset Creation (555 labeled examples)  | Complete (provisional; independent expert label review pending)                                                                                                                                                                                                                                                                   |
| 3. Baseline ML Model                        | Complete                                                                                                                                                                                                                                                                                                                          |
| 4. Improved ML Model (embedding comparison) | Comparison complete. Decision reopened: the embedding model becomes the permanent classifier once the Python backend is restored, which requires re-running the evaluation suite.                                                                                                                                                 |
| 5. Safety Rule Engine (21 rules)            | Complete                                                                                                                                                                                                                                                                                                                          |
| 6. Backend APIs                             | Complete                                                                                                                                                                                                                                                                                                                          |
| 7. Frontend Chat Flow                       | Complete, verified live                                                                                                                                                                                                                                                                                                           |
| **8. Testing & Deployment**           | **In progress.** Clerk auth migration done; unit tests and port-equivalence gates done. Remaining: restore the FastAPI backend and Postgres schema, swap in the embedding classifier and re-run the evaluation suite, API integration tests, UI smoke tests for the 4 demo scenarios, deployment to Render, seed/demo data. |
| 9. Documentation & Final Demo               | Not started. Final evaluation report, screenshots and demo script for all 5 risk levels, future-work section, dry-run demo.                                                                                                                                                                                                       |

Seven of nine phases are fully complete with measured exit-check evidence rather than best-effort claims. What remains in Phase 8, namely the backend reversion, the classifier swap, integration and smoke tests, deployment, and demo data, together with Phase 9, which writes up results that largely already exist rather than producing new ones, is materially smaller in scope than what has already shipped. Much of Phase 9 is packaging, since `ml/eval/` already contains most of the metrics that phase needs to report.

The two planned changes add work to Phase 8 and the report should say so rather than absorb them silently, but neither is open-ended. Restoring the FastAPI backend recovers an implementation that exists in version control and was already proven equivalent to what currently runs, so the effort is dominated by re-hosting and re-testing rather than by design. Adopting the embedding classifier means retraining on the existing 555-example corpus, which is a short job, and re-running the evaluation and held-out suites that are already written. The genuinely uncertain item is not either change itself but whether the embedding model fits inside the free tier's memory ceiling, which is why Section 3 recommends measuring that locally before the deployment window rather than during it. With that measurement taken early, schedule risk remains low relative to a typical FYP at this stage.

---

## 8. Overall Feasibility Recommendation

CanIDIY is feasible and substantially de-risked. That is an unusual position for a feasibility report to argue from, since most such reports are written before implementation begins, and the strongest evidence here is not architectural promise but measured results: a working, CI-gated, cross-verified system spanning frontend, backend, database, machine learning, and a safety-critical rule engine, already exercised end to end against real rather than scripted data across all five risk tiers.

Several honest caveats should be stated plainly rather than smoothed over. Supervisor sign-off on the scope decisions is still provisional. The dataset label quality is self-audited rather than independently verified by an expert. Raw ML classifier accuracy is modest, compensated in deployment by much stronger rule-engine recall. And two planned changes, the reversion to a FastAPI backend on Render and the permanent adoption of the sentence-embedding classifier, were pending at the time of writing, so the measured figures in Section 3 describe the implementation currently running and will need re-running against the new one. Evaluators tend to read selective disclosure as a red flag and honest disclosure of known limitations as evidence of engineering maturity, and this project has the artifacts to support the latter: documented CI gates, a held-out validation protocol committed before the rules it tests, and explicit "do not report this number alone" notes in the project's own working documents.

The recommendation is to proceed with completing Phase 8, including the backend reversion, the classifier change, and deployment, followed by Phase 9 documentation and demonstration. No architectural, economic, legal, or schedule blocker was found that would require a scope change beyond what has already been cut proactively, namely the admin dashboard and the professional and vendor marketplace. The one item warranting active management rather than mere monitoring is the interaction between the embedding model's memory footprint and the free hosting tier's 512 MB ceiling, which should be measured early enough that an upgrade, if needed, is a budgeting decision rather than a deployment-day emergency.

---

## 9. Related Work and Existing Systems

Several commercial products occupy adjacent space, but none treat risk triage as the product itself, which is where CanIDIY differentiates.

| Existing System            | Typical Focus                                                                | CanIDIY Differentiation                                                                                          |
| -------------------------- | ---------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| ChatDIY.ai                 | DIY planning, measurements, tools, materials, budgets, step-by-step guidance | Risk classification is the core product, not a supporting feature                                                |
| Home Depot Magic Apron     | Generative AI assistant for home-improvement Q&A and product pages           | Not retail-first; safety triage and escalation come before any how-to content                                    |
| Lowe's Mylow               | AI advisor for home-improvement questions and product recommendations        | Focuses on*whether* the task should be attempted at all, not just how                                          |
| Generic ChatGPT DIY advice | Natural-language answers dependent on prompt quality                         | Structured, auditable rule engine plus trained classifier and hardcoded escalation floors, not a single LLM call |

If the handbook requires a formal literature review, this table can be extended with two or three academic citations on hybrid ML and rule-based safety classification, and on TF-IDF versus sentence-embedding text classification over small domain-specific corpora. Both topics are directly demonstrated by the Phase 3 and Phase 4 experiment described in Section 3 and would cite naturally from there.

---

## Notes for finalizing this report

Two further points are worth keeping in mind. Section 5 (legal and ethical) and Section 7 (schedule) are the strongest sections given the project's current state, so lead with them in any oral defence. If the submission format allows appendix references, cite `ml/eval/comparison_report.md`, `ml/data/REVIEW.md`, and `phases.md` directly as evidence, since they hold the primary results this report summarises.
