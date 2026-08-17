# CanIDIY: Feasibility Report

**A Risk-Aware Construction Task Assessment and Tool Recommendation Platform**

Final Year Project, School of Computing, FAST NUCES

| Field           | Value                                                        |
| --------------- | ------------------------------------------------------------ |
| Project Title   | CanIDIY                                                       |
| Project Type    | Product-Based FYP (AI/ML, Web Platform, Database)            |
| Team            | Muhammad Sarim Khan Ghouri (23k0720), Areeb ur Rehman (23k0682), Syed Ammar Ali (23k0740) |
| Supervisor      | Zain ul Hassan                                                |
| Department      | School of Computing, FAST NUCES                               |
| Duration        | 12 months                                                     |
| Date            | 15 August 2026                                                |

---

## Executive Summary

CanIDIY decides whether a DIY or small construction task is safe for a non-expert to attempt, and then supports them through whatever the safe course of action turns out to be. A user describes a task in plain language, the system asks clarifying questions, and it returns one of five risk levels together with an explanation, the tools and protective equipment required, and, depending on that risk level, either guidance for doing the task or help finding a professional.

This report assesses whether that system can be delivered as a twelve-month Final Year Project. The project is in its first quarter, and development so far has deliberately front-loaded the component carrying the greatest technical risk: the hybrid risk engine that decides how dangerous a task is. That component is built and validated, which means the principal question a feasibility report exists to answer, whether the core idea works at all, can be answered with evidence rather than argument.

The remaining programme is substantial and spans five further capabilities, described in Section 3.2, together with the evaluation, deployment, and documentation work needed to bring them to a demonstrable standard.

No blocker was found under any of the five dimensions examined:

- **Technical.** The risk engine already exists and passes tests designed to attack it. The planned capabilities extend a proven foundation rather than resting on an unproven one.
- **Economic.** The system runs on managed hosting at close to zero cost, with small, bounded spending on external services.
- **Legal and ethical.** The principal risk, an AI system giving unsafe advice with false authority, is prevented structurally rather than by policy. A language model cannot assign a risk level in this architecture, and every planned feature preserves that boundary.
- **Operational.** The interface follows conventions its non-technical audience already knows, validated by real end-to-end use.
- **Schedule.** Nine months remain against a defined set of workstreams that can be sequenced independently, so schedule pressure can be absorbed by reducing depth rather than abandoning capabilities.

Two limitations are disclosed rather than smoothed over. The dataset's safety labels were audited by the team against published safety standards rather than verified by an independent licensed tradesperson. And the machine learning classifier's standalone accuracy is modest, which the design anticipates: the rule engine, not the classifier, is what makes the system safe.

**Recommendation: proceed.**

---

## 1. Purpose and Scope

This report assesses whether CanIDIY can be completed as a twelve-month Final Year Project within the skills and resources available to a three-member team. Section 3 describes the system, separating what is already built from what is planned. Sections 4 to 8 examine technical, economic, legal, operational, and schedule feasibility in turn. Section 9 lists the identified risks and Section 11 gives the recommendation.

---

## 2. What CanIDIY Does

CanIDIY lets a non-expert describe a DIY or small construction task in natural language and decides, before offering any other help, whether the task is safe to attempt at all. The system asks clarifying follow-up questions, classifies the task into one of five risk levels running from Safe DIY through to Dangerous or Do Not Attempt, and explains the decision in plain language.

That risk level then determines what happens next. A task judged safe leads to tool and material recommendations and step-by-step guidance. A task judged to need professional involvement leads instead to help finding a qualified professional nearby, with no how-to guidance at all. A task judged dangerous receives the strongest form of that referral, alongside the immediate safety action to take, since a dangerous task needs a professional more urgently rather than less.

The intended users are homeowners, tenants, and small property owners with no construction expertise, who currently face a choice between guessing and paying for a professional assessment they may not need.

**The defining constraint of the design is that the final risk level is never decided by an AI language model.** Risk is the higher of two independent judgements: a trained classifier, and a fixed catalog of hazard rules written and reviewed by hand. Those rules can only raise a risk level, never lower one. The language model is restricted to phrasing questions, writing explanations from fixed templates, and identifying which of the existing hazard rules apply. It cannot invent a rule and it cannot assign a risk number.

This separation is the single most important fact about the project. It makes the system's safety behaviour auditable, and it means the product's safety does not depend on an AI model behaving well. Every capability described below sits on the safe side of that boundary.

---

## 3. The System

### 3.1 The delivered core

Development to date has concentrated on the risk engine, because a failure there would invalidate the product concept regardless of how well anything else worked. That engine, the conversational interface that feeds it, and the account system around it are built and tested.

- **Interface.** A web application built with Next.js and TypeScript, hosted on Vercel.
- **Service and database.** A FastAPI service over a Postgres database, hosted on Render.
- **Accounts.** Clerk, integrated so that the team's own interface design is preserved rather than replaced by off-the-shelf components.
- **Risk classifier.** A sentence-embedding model with a classification head, trained on a hand-labelled corpus of DIY and construction tasks.
- **Rule engine.** 21 hand-written hazard rules, each able only to raise a risk level, evaluated independently of the classifier.
- **Language model.** Reached through a single controlled component, with every response validated against a fixed schema before it is used anywhere.

The classifier representation was selected by experiment rather than assumption. Two candidate approaches were trained and scored on identical data so the comparison isolated the representation itself. They performed equivalently at the current dataset size, but an analysis of accuracy against training volume showed the simpler approach had stopped improving while the embedding approach was still gaining. The embedding model was chosen on that basis, and the training corpus is being expanded to more than double its current size to reach the point where the advantage becomes measurable.

### 3.2 Planned capabilities

Five further capabilities make up the bulk of the remaining programme. Each is stated with the constraint that keeps it on the safe side of the architectural boundary described in Section 2.

**Photo attachment and image-assisted hazard identification.** Users will be able to attach photographs of the task area during intake. Images give the system evidence a text description often omits, such as visible corrosion, an unlabelled fuse box, or the true scale of a job. Images are used only to help identify which of the existing hazard rules apply, exactly as task text already is. They cannot assign a risk level, and structural diagnosis by computer vision remains out of scope. Where an image is ambiguous, the system treats the hazard as present rather than absent, consistent with how it already handles unanswered questions.

**Retrieval-augmented tool and material recommendation.** A retrieval system over a curated catalog of tools, materials, and protective equipment will replace generic suggestions with specific, grounded ones, including substitutes when an item is unavailable. Retrieval is grounded in the catalog rather than generated freely, so recommendations can be traced to a source. This capability reuses the vector storage already present in the database. It advises on equipment only and has no influence on the risk decision.

**Step-by-step guidance for low-risk tasks.** Tasks classified as safe for a non-expert will receive structured walkthroughs. This capability is strictly gated on the risk assessment: guidance is generated only after a task has been classified at the lowest risk levels, and is withheld entirely from tasks requiring professional involvement. The gate is the point. Rather than weakening the product's founding principle that it decides whether a task should be attempted, this makes the risk decision the precondition for any instruction at all, which is a stronger position than offering guidance unconditionally.

**Professional discovery via mapping services.** Tasks classified as requiring professional involvement will surface relevant qualified trades nearby, using a mapping and places service. This is directory lookup rather than a marketplace: there are no professional accounts, no quote routing, no payment handling, and no claim about the quality of any listed business. The product's job still ends at recommending that a professional be engaged, and this capability makes that recommendation actionable rather than abstract.

**Urdu and multilingual support.** The interface and task intake will support Urdu alongside English, so users can describe tasks in the language they think in. This materially widens the addressable audience and is the capability with the most significant technical implications, discussed in Section 4.

Two of these capabilities extend boundaries drawn in the project's original scope document, which lists professional connection and how-to guidance as outside the initial release. Both are deliberate expansions rather than oversights, and both are constrained as described above so that the safety architecture is unchanged. The scope document will be updated to match.

---

## 4. Technical Feasibility

The technical question is whether this system can be built with the skills and time available. The evidence for the core is direct, and the planned capabilities are individually well understood.

**The safety-critical component is verified, not asserted.** The rule engine is covered by property tests including deliberately hostile inputs, such as invented rule identifiers returned by the language model and text shaped like a database injection attack. These confirm that the language model cannot introduce a rule outside the reviewed catalog. A regression gate replays a large body of rule evaluations against an approved baseline whenever the rules change, so any alteration to what the product calls safe appears as a reviewable difference rather than a silent change in behaviour.

**Accuracy on the cases that matter is measured and corroborated.** Recall on the two most severe risk levels is 0.902 for the combined system. This is supported by a held-out set of 24 tasks, 14 of them deliberately designed to slip past the rules, which was written and locked before the rules it tests, and which the system caught in full. Fixing a test set before the thing it tests is the strongest available evidence that the result reflects genuine capability rather than tuning to the test.

**The classifier is deliberately not load-bearing.** Its standalone accuracy is modest and short of the project's provisional target. This is disclosed plainly because the architecture anticipates it. Since the final risk level is the higher of classifier and rules, and the rules can only escalate, a classifier that under-predicts is corrected rather than trusted. The classifier sharpens the system's judgement on tasks the rules do not cover; it is not what makes the system safe. The main constraint on its accuracy is the volume of labelled data, which is what the dataset expansion addresses.

**The planned capabilities carry different levels of technical risk**, and the report distinguishes them rather than treating them as uniform:

- **Retrieval-based recommendation is low risk.** The database already provides vector storage, so the infrastructure exists. The work is curating the catalog and tuning retrieval quality, both of which are effort rather than uncertainty.
- **Professional discovery is low risk.** Mapping and places services are mature, well documented, and straightforward to integrate. The main considerations are commercial rather than technical and are covered in Section 5.
- **Photo attachment is moderate risk.** Storage, upload handling, and privacy controls are routine. The judgement required is in deciding how much weight image-derived signals should carry when identifying hazards, which is a design question to be settled conservatively rather than a technical obstacle.
- **Guided walkthroughs are moderate risk.** The engineering is straightforward, but the content must be constrained so that guidance never drifts beyond the task that was actually assessed. This will be handled with templated structures and explicit gating on risk level, in the same manner as the existing explanation system.
- **Multilingual support is the highest-risk item and needs a decision early.** The current classifier is trained on English text and will not transfer to Urdu unaltered. Two approaches are viable: translate incoming text to English before classification, which preserves the existing model but introduces a translation step whose errors would affect safety decisions; or move to a multilingual embedding model, which handles both languages natively but requires re-validating the classifier and re-running the evaluation suite. The second is the more robust option and is the current preference. Either way, hazard rule matching and the wording of safety explanations must be validated separately in each language, because a mistranslated safety warning is a safety defect rather than a cosmetic one.

**One deployment constraint requires measurement.** The chosen hosting tier provides 512 MB of memory, and the embedding model may not fit within it alongside the application. Several mitigations exist, from serving the model in a lighter runtime through to moving to a low-cost paid tier. This should be measured before it is committed to, and a multilingual model, being larger than an English-only one, makes the measurement more pressing.

---

## 5. Economic Feasibility

The cost of building and demonstrating the system is small and bounded.

Hosting runs on managed platforms whose free tiers cover the scale required, meaning demonstration use rather than production traffic. The interface, the service, the database, and the account system all sit within free allowances. Two caveats apply and are worth stating in advance rather than discovering late: free database instances on the chosen platform expire 30 days after creation, and the free service tier's memory limit may force an upgrade as described above. Either would mean a small monthly fee on the order of a single low-cost instance, not a change in the project's economics.

Three external services carry costs that scale with use rather than being flat:

- **Language model usage** is inexpensive because of the safety architecture rather than in spite of it. The model is used only for phrasing, tagging, and generating guidance from templates, never for risk decisions, so calls are short and few per assessment. The team intends to purchase a small amount of credit so that rate limits cannot disrupt a live demonstration. This is insurance rather than a running cost, and the system degrades gracefully without a key.
- **Mapping and places services** require a billing-enabled account. Providers offer a monthly free allowance that comfortably covers development and demonstration traffic, but the account must be configured with usage caps so that a misconfigured loop cannot generate unexpected charges. This should be set up early and verified against current pricing rather than assumed.
- **Image storage** grows with usage. At demonstration scale it is negligible, and uploads will be size-limited and format-restricted, which bounds it further.

No paid tooling is required for development. The entire toolchain is open source. Scaling the system beyond a student project would introduce genuine hosting, mapping, and API costs driven by user volume, which falls outside this assessment but is noted so the current arrangement is not read as scaling unchanged.

---

## 6. Legal and Ethical Feasibility

This dimension deserves the closest scrutiny, because the product gives safety-relevant advice to people without professional training, and the planned capabilities widen that responsibility.

**Liability posture.** CanIDIY is a decision-support tool, not a certified safety authority. Rule explanations are deliberately jurisdiction-neutral, stating a hazard and its consequence rather than citing particular regulations or building codes, because the project does not target a single regulatory jurisdiction and should not claim authority it cannot substantiate. Every presentation of the product is explicit that it augments professional judgement rather than replacing it.

**Safety guarantees enforced in code.** Four constraints function as ethical risk mitigation, and each is enforced by the software rather than by policy:

- The language model never assigns a risk level, and any hazard it identifies outside the reviewed catalog is discarded rather than accepted.
- Unanswered safety-critical questions, and answers of "unsure", raise the risk level to the worst plausible case rather than assuming safety.
- Any failure in the AI pipeline marks the assessment as failed and blocks the recommendation outright. There is no fallback to a safe-looking result.
- Every assessment, including every failure, is logged, which supports an audit trail if accountability is ever questioned.

**Additional obligations created by the planned capabilities.** Three deserve explicit statement:

- **Guided walkthroughs** raise the consequences of a misclassification, because a task wrongly judged safe would now receive instructions rather than only a label. This is why guidance is gated on the risk decision rather than offered alongside it, and why the conservative bias of the rule engine matters more, not less, as the product grows.
- **Professional listings** must not imply endorsement. The system surfaces businesses from a mapping provider and makes no claim about their competence, licensing, or insurance. This must be stated in the interface, not only in documentation.
- **Photographs of a user's home** are more sensitive than task descriptions. They will be stored against the owning account under the same access rules, restricted in size and format, and deletable by the user.

**Data privacy.** Task descriptions and uploaded images are personal data. Each is stored against its owner's account, and a request for another user's record returns "not found" rather than "access denied", so the existence of other users' records is never disclosed.

**A disclosed limitation.** The dataset's high-risk labels were audited against 11 published safety standards, including HSE guidance, the OSHA Focus Four, and UK regulations covering gas safety, asbestos, electrical work, and confined spaces, reaching full conformance after corrections. That audit was carried out by the team. It is not independent expert verification, and this report states so plainly. Having a licensed tradesperson review a blind sample is identified as future work, and the dataset expansion is the natural point at which to obtain it.

---

## 7. Operational Feasibility

**Usability.** The interface is a conversation rather than a form, and its visual language is kept deliberately close to ChatGPT: a centred message thread, clearly distinguished turns, a persistent composer, and a collapsible history sidebar. This is a deliberate decision. Consumer chat assistants have become the reference interface for describing a problem in one's own words, so borrowing their conventions means a first-time user arrives already knowing how to operate the product and spends their attention on describing the task rather than learning the interface. The benefit is largest precisely for the non-technical audience CanIDIY targets. Quick-reply buttons for follow-up questions extend the same principle, letting a user answer a safety-critical question with one tap rather than composing a sentence, which reduces both effort and the chance of an ambiguous answer.

Adding photographs, guidance, listings, and a second language all fit this model without restructuring it, since each appears as another kind of turn in an existing conversation rather than as a new screen to learn.

Usability has been validated rather than assumed. The complete user journey, from registration through task submission, follow-up questions, receiving an assessment, and revisiting history, has been tested end to end in a real browser across all five risk levels against a live service.

**Maintainability.** The hazard catalog is intentionally not editable through an administrative interface. Changes pass through code review and redeployment instead. A three-person team cannot realistically build, secure, and test a full administrative system while keeping the safety guarantee airtight in the same timeline, so this decision reduces the surface that must be built and tested. It also means the catalog cannot be altered by anyone without a reviewed change, which is itself a safety property.

**Team capacity.** Five capabilities across three people over nine months is a realistic load precisely because they are separable. Retrieval, mapping, and image handling touch different parts of the system and can proceed in parallel, and each can be reduced in depth without being abandoned if time tightens.

---

## 8. Schedule Feasibility

The project is planned as a twelve-month effort and is currently in its first quarter, leaving roughly nine months. Work so far has been deliberately front-loaded onto the risk engine, so the highest technical uncertainty has been retired early rather than left to be discovered late.

The remaining programme is organised into workstreams that can largely proceed in parallel:

| Workstream | Scope | Indicative window |
| ---------- | ----- | ----------------- |
| Dataset expansion and model programme | More than double the labelled corpus, refit and re-compare models, calibrate confidence | Months 3 to 7, continuous |
| Photo attachment and image-assisted tagging | Upload, storage, privacy controls, integration into hazard identification | Months 3 to 6 |
| Retrieval-based tool recommendation | Catalog curation, retrieval over existing vector storage, substitute handling | Months 4 to 7 |
| Step-by-step guidance for low-risk tasks | Templated walkthrough generation, strict gating on risk level | Months 5 to 8 |
| Professional discovery | Mapping and places integration, listing presentation, disclaimers | Months 6 to 8 |
| Urdu and multilingual support | Multilingual model decision, interface localisation, per-language safety validation | Months 6 to 10 |
| Evaluation, deployment, and documentation | Integration and usability testing, production deployment, final report and demonstration | Months 9 to 12 |

Two properties of this plan support the schedule assessment. First, the workstreams are separable, so a delay in one does not stall the others. Second, each has a reducible depth: the tool catalog can cover fewer categories, guidance can cover fewer task types, and multilingual support can launch with a narrower feature surface, without any capability being dropped entirely. Schedule pressure can therefore be absorbed by narrowing rather than abandoning, which is the property that most distinguishes a plan that survives contact with reality.

The item requiring early attention is the multilingual model decision described in Section 4, because it determines whether the classifier is re-validated once or twice, and because a multilingual model interacts with the hosting memory limit. Both should be settled well before the localisation work begins.

---

## 9. Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
| - | ---- | ---------- | ------ | ---------- |
| 1 | Multilingual support requires re-validating the classifier and degrades safety accuracy in the second language | Medium | High | Decide the model approach early. Validate hazard matching and safety wording separately per language. Treat a mistranslated warning as a defect, not a cosmetic issue. |
| 2 | Embedding model, particularly a larger multilingual one, exceeds the hosting tier's memory limit | Medium | High | Measure before committing. Serve the model in a lighter runtime, precompute where possible, or move to a low-cost paid tier. |
| 3 | Guided walkthroughs increase the consequence of a misclassification | Low | High | Gate guidance strictly on the risk decision, withhold it entirely above the low-risk tiers, and keep the rule engine's conservative bias intact. |
| 4 | Free database instance expires before the demonstration | Medium | High | Maintain a script that rebuilds the database from scratch, create the production instance close to the demonstration, or budget for a paid instance. |
| 5 | Breadth of planned capabilities exceeds team capacity | Medium | Medium | Workstreams are separable and each has reducible depth. Narrow scope within a capability rather than dropping it. |
| 6 | Mapping service costs exceed the free allowance through misconfiguration | Low | Medium | Configure usage caps and alerts when the account is created, and verify against current pricing. |
| 7 | Professional listings are read as an endorsement | Medium | Medium | State plainly in the interface that listings are drawn from a mapping provider and carry no claim about competence, licensing, or insurance. |
| 8 | Dataset labels are team-audited rather than expert-verified | Confirmed | Medium | Disclosed openly. Independent expert review sought alongside the dataset expansion. |
| 9 | Service start-up delay during a live demonstration | High | Low | Warm the service shortly beforehand. |

---

## 10. Related Work

Several commercial products occupy adjacent space, but none treats risk assessment as the gate through which everything else must pass, which is where CanIDIY differentiates.

| Existing System | Typical Focus | CanIDIY Differentiation |
| --------------- | ------------- | ----------------------- |
| ChatDIY.ai | DIY planning, measurements, tools, materials, budgets, step-by-step guidance | Guidance is withheld until a task has been judged safe, rather than offered on request |
| Home Depot Magic Apron | AI assistant for home-improvement questions and product pages | Not retail-first. Safety assessment and escalation precede any recommendation |
| Lowe's Mylow | AI advisor for home-improvement questions and product recommendations | Determines whether a task should be attempted at all, then adapts what it offers to that answer |
| Generic AI chat advice | Natural-language answers dependent on how the question is asked | A structured, auditable rule engine and trained classifier with fixed escalation thresholds, rather than a single AI response |

---

## 11. Recommendation

CanIDIY is feasible as a twelve-month Final Year Project, and the strongest evidence is that the hardest part is already working. The risk engine, which is the component on which the entire product concept depends, is built, tested against deliberately hostile input, and protected against silent regression. That removes the question of whether the idea is achievable and leaves a programme of capability development on a proven foundation.

The remaining nine months carry a substantial and clearly defined body of work: five new capabilities spanning image handling, retrieval, guided content, third-party integration, and multilingual support, together with a machine learning programme to expand and revalidate the training data, and the evaluation and deployment work needed to bring all of it to a demonstrable standard.

Two limitations are stated plainly. Dataset label quality is team-audited rather than independently verified by a qualified tradesperson. Standalone classifier accuracy is modest, which the architecture anticipates by making the rule engine, not the classifier, the component that carries the safety guarantee.

No architectural, economic, legal, or schedule blocker was identified. The recommendation is to proceed. Two items warrant active management rather than monitoring: the approach to multilingual classification, which should be decided early because it determines how often the classifier must be revalidated, and the embedding model's memory footprint against the hosting tier's limit, which should be measured early enough that an upgrade, if needed, is a budgeting decision rather than a deployment-day emergency.

---

*Prepared by Muhammad Sarim Khan Ghouri, Areeb ur Rehman, and Syed Ammar Ali. School of Computing, FAST NUCES, 15 August 2026.*
