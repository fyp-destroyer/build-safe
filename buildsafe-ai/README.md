# BuildSafe AI / ConstructMate

BuildSafe AI is a safety-first DIY and construction assessment MVP for an FYP supervisor demo. The product accepts a natural-language task, identifies the likely `task_intent`, asks at most 1-2 safety-critical follow-up questions, and then returns a structured risk decision with tools, materials, PPE, warnings, professional guidance, and an explainable risk score breakdown.

For repository-wide product constraints and development rules, see [PROJECT_INSTRUCTIONS.md](PROJECT_INSTRUCTIONS.md).

## Project Overview

- Backend: FastAPI, Pydantic, deterministic rule engine, optional Gemini augmentation
- Frontend: React, Vite, Tailwind CSS chat UI
- Optional LLM layer: Gemini for task understanding, follow-up planning, update parsing, and explanation assistance
- Final safety authority: deterministic rule engine plus explainable risk rubric
- Update flow: completed assessments stay in a frontend session so the user can correct details without starting over

## How To Run

Backend:

```bash
cd buildsafe-ai/backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd buildsafe-ai/frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

## Gemini Configuration

Create or update [backend/.env](backend/.env) from [backend/.env.example](backend/.env.example):

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-flash-latest
GEMINI_ENABLED=true
DEBUG_TRACE_ENABLED=true
```

Notes:

- `GEMINI_ENABLED=true` turns on Gemini-assisted follow-up planning, update parsing, and explanation support.
- `GEMINI_ENABLED=false` keeps the MVP fully usable with deterministic fallback behavior.
- `DEBUG_TRACE_ENABLED=true` allows the backend to return `debug_trace` data for the Developer Trace panel.
- Do not commit a real Gemini API key.

## Developer Trace Panel

Enable the frontend panel in [frontend/.env.example](frontend/.env.example) or your local frontend env:

```env
VITE_SHOW_DEBUG_PANEL=true
```

Developer Trace behavior:

- The panel is visible only in local development.
- The frontend toggle alone only shows the container.
- The backend must also set `DEBUG_TRACE_ENABLED=true` to return Gemini and rule-engine details.

## Architecture Summary

`task_intent`

- The backend classifies the user request into a concrete intent such as `hanging_wall_decor`, `wall_painting`, `ceiling_fan_installation`, `wall_demolition`, or `plumbing_leak_repair`.
- This prevents ambiguous tasks such as "painting" from being confused with room painting when the user actually means framed artwork.

Rule engine

- The rule engine is the final decision-maker.
- It checks task keywords, follow-up answers, risk signals, and safety rules.
- It also enforces conservative outcomes for hazardous utility, structural, gas, and demolition tasks.

Gemini augmentation

- Gemini can help with task interpretation, follow-up planning, update parsing, selected explanation text, and debug visibility.
- Gemini does not override the final safety authority of the rule engine.
- If Gemini is disabled, missing, or fails, the MVP falls back automatically.

Update parsing

- After a final assessment is shown, the user can keep typing in the same chat to correct or add details.
- The frontend sends those messages to `POST /api/update-assessment` instead of starting a fresh task.
- Example update: `Actually, the painting is 2 kg.`
- The backend detects changed information, merges it into the previous context, reruns the risk engine, and returns what changed and what stayed the same.
- Gemini may parse natural-language updates when `GEMINI_ENABLED=true` and `GEMINI_API_KEY` is available.
- If Gemini is disabled, missing, or fails, fallback rules still detect common updates such as weight, wall material, attachment method, hidden wiring, available tools, skill level, and exposed electrical damage.
- The rule engine remains the safety authority. Gemini can help read the update, but it does not directly decide the final risk level.

Assessment session state

After the first completed assessment, the frontend keeps an `activeAssessmentSession` with:

- original task description
- task intent and task category
- collected follow-up answers
- user context such as skill level, tools, location, urgency, and budget
- latest assessment
- assessment history
- action plan and action plan status

This lets the MVP show a corrected assessment without losing the original task or asking the user to repeat the full flow.

Impact-aware updates

Not every update changes every section. For example, changing a painting from `1 kg` to `2 kg` may affect:

- risk score
- materials
- safety warnings

But it should usually preserve:

- task intent
- task category
- basic tools

The response highlights the focused difference instead of pretending the whole assessment changed.

Action plan invalidation

- If an action plan already exists and the updated assessment changes important safety assumptions, the frontend marks the old plan as outdated.
- Invalidation can be triggered by risk level changes, a significant risk score increase, changed safety warnings, changed professional recommendation, changed task intent, or changed required method/materials.
- Dangerous updates, exposed wiring, hidden utilities, and professional-only outcomes should not continue showing old safe-DIY steps.
- The UI shows: `Your previous plan may no longer be valid because the risk assessment changed.` and offers `Regenerate Plan`.

Risk score rubric

- `base_task_risk`: `0-30`
- `hazard_severity`: `0-25`
- `skill_mismatch`: `0-15`
- `tools_ppe_readiness`: `0-15`
- `environment_urgency_unknowns`: `0-15`
- Final score: total out of `100`

Risk thresholds:

- `0-20`: Safe DIY
- `21-40`: DIY with supervision
- `41-60`: Professional recommended
- `61-80`: Professional required
- `81-100`: Dangerous / permit-required / do not attempt

Safety overrides

- Certain triggers can escalate the final risk level even if the numeric score is lower.
- Current examples include gas line work, main electrical panel, exposed wiring, load-bearing uncertainty, structural demolition, roof work at height, water near electricity, and hidden-utility uncertainty during demolition or drilling.

## Demo Test And Sample Cases

These cases are documented in the MVP and covered by the backend smoke tests in [backend/tests/test_demo_cases.py](backend/tests/test_demo_cases.py).

1. `I want to hang a new painting in my bedroom.`
   Expected: `hanging_wall_decor`, carpentry-style follow-up questions about weight and wall/attachment method, no paint tools or drying time, final risk usually `Safe DIY` or `DIY with supervision`.
2. `I want to paint my bedroom.`
   Expected: `wall_painting`, painting tools and materials, drying time in the estimate, usually a lower-risk result.
3. `I want to hang a heavy mirror on a tiled bathroom wall.`
   Expected: still treated as wall decor rather than room painting, no paint tools, higher risk than a simple lightweight frame, anchors and handyman/carpenter guidance if unsure.
4. `I want to install a ceiling fan.`
   Expected: `ceiling_fan_installation`, electrical category, voltage tester and insulated-tool requirements, electrician recommendation for beginner users.
5. `I want to break a wall between my kitchen and living room.`
   Expected: `wall_demolition`, conservative structural/utility checks, professional-only outcome, no unsafe demolition walkthrough.
6. `I want to replace a light bulb.`
   Expected: `light_bulb_replacement`, 0-1 follow-up question, no budget question, usually `Safe DIY` unless wiring or height risk appears.
7. `I want to fix a leaking pipe.`
   Expected: `plumbing_leak_repair`, asks about minor vs hidden leak and nearby electrical exposure, score changes based on the answers, plumber recommendation when needed.

## Update Assessment Demo Cases

These cases demonstrate the completed-assessment update flow. Backend parser and reassessment tests live in [backend/tests/test_update_assessment.py](backend/tests/test_update_assessment.py).

1. Initial: `I want to hang a new painting in my bedroom.`
   Answer: `It weighs 1 kg and I will drill.`
   Update: `Actually, it weighs 2 kg.`
   Expected: same `hanging_wall_decor` intent, slight risk increase if needed, tools mostly unchanged, no paint tools, and a changed-vs-unchanged summary.
2. Initial: `I want to hang a painting using adhesive strips.`
   Update: `Actually, it is 8 kg.`
   Expected: risk increases, adhesive-only mounting may be unsafe, stronger anchors or handyman guidance may appear, and any old safe plan is invalidated.
3. Initial: `I want to hang a frame and I will drill.`
   Update: `There may be electrical wiring behind the wall.`
   Expected: risk increases significantly, drilling guidance is restricted, professional help is recommended, and any old drilling plan is invalidated.
4. Initial: `I want to paint my bedroom.`
   Update: `There is mold and dampness on the wall.`
   Expected: task intent remains `wall_painting`, while warnings, PPE, time, and preparation guidance may change.
5. Initial: `I want to replace a light bulb.`
   Update: `The holder is damaged and I can see wires.`
   Expected: risk escalates, an electrician is recommended, and any simple DIY plan is invalidated.

## Supervisor Demo Script

1. Start the backend and frontend.
2. Explain that the MVP separates `task_intent`, follow-up planning, final rule-engine decision, and explainable score breakdown.
3. Turn on Gemini and Developer Trace.
4. Show `I want to hang a new painting in my bedroom.` and highlight correct intent detection.
5. Answer the follow-up with a safe simple case such as `It weighs 1 kg and I will drill.`
6. Show the final risk assessment card and open `Why this score?` to walk through the rubric.
7. Generate a safe action plan if the plan button is available.
8. Continue in the same chat with `Actually, it weighs 2 kg.`
9. Show that the assessment updates in place instead of restarting the assessment flow.
10. Point out `What changed?` and `What stayed the same?`
11. If the risk change invalidates the old plan, show the outdated-plan warning and `Regenerate Plan`.
12. Open Developer Trace, if enabled, and point out update parsing, fallback/Gemini status, triggered rules, and final rule-engine decision.
13. Optionally show `I want to paint my bedroom.` to demonstrate a separate new task and `I want to break a wall between my kitchen and living room.` to demonstrate conservative escalation.

## Supervisor Demo Checklist

- Start backend
- Start frontend
- Enable Gemini
- Enable Developer Trace
- Test `hang a painting`
- Test an update after the completed painting assessment
- Test `paint bedroom`
- Test `break a wall`
- Show risk score breakdown
- Show changed vs unchanged update summary
- Show old plan invalidation when risk changes
- Show LLM-assisted label
- Show rules triggered and final risk decision

## Running The Demo Smoke Tests

```bash
cd buildsafe-ai/backend
python -m unittest discover -s tests -v
```

The smoke suite verifies the seven documented sample cases plus the update-assessment parser/reassessment cases. It catches regressions in task intent, follow-up planning, recommendation consistency, risk behavior, and changed-vs-unchanged update summaries.

## Known Limitations

- The MVP relies on rule-based heuristics and curated seed data rather than a production knowledge base.
- Tool availability is inferred from short user inputs and can still be incomplete.
- The current system does not yet parse photos or inspect the worksite visually.
- Risk scoring is explainable, but still intentionally conservative for ambiguous structural or utility work.
- Recommendation catalogs and pricing are placeholder-level rather than market-connected.

## Future Work

- RAG-based hardware and tool database
- Product recommendations with brand and price comparison
- Professional marketplace integration
- Quote request system
- Image and photo upload
- PostgreSQL migration
- ML classifier training for task intent and risk priors
