# BuildSafe AI Backend

This FastAPI backend powers the BuildSafe AI / ConstructMate MVP. It handles task-intent detection, Gemini-assisted follow-up planning, recommendation consistency checks, rule-based safety logic, and the final explainable risk-score breakdown.

## Environment Setup

Copy [`.env.example`](.env.example) to `.env` and configure:

```env
GEMINI_API_KEY=
GEMINI_MODEL=gemini-flash-latest
GEMINI_ENABLED=false
DEBUG_TRACE_ENABLED=false
FRONTEND_ORIGINS=http://localhost:5173,http://localhost:5174
```

What each setting does:

- `GEMINI_API_KEY`: Gemini API key for optional LLM augmentation
- `GEMINI_MODEL`: Gemini model name, default `gemini-flash-latest`
- `GEMINI_ENABLED`: enables Gemini-assisted task understanding, follow-up planning, and update parsing
- `DEBUG_TRACE_ENABLED`: returns backend debug trace payloads for the frontend Developer Trace panel
- `FRONTEND_ORIGINS`: comma-separated list of deployed frontend origins allowed by CORS, such as Vercel or ngrok URLs

Fallback behavior:

- If Gemini is disabled, missing, or fails, follow-up planning and update parsing fall back to deterministic rules.
- The final risk level always remains under rule-engine control.

## Run Locally

```bash
cd buildsafe-ai/backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open the API docs:

```text
http://localhost:8000/docs
```

Check backend health:

```text
http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "BuildSafe AI Backend"
}
```

## CORS And Deployment

The backend always allows local frontend development origins:

- `http://localhost:5173`
- `http://localhost:5174`
- `http://localhost:3000`

It also reads additional allowed frontend origins from `FRONTEND_ORIGINS`. Use a comma-separated list with no trailing path:

```env
FRONTEND_ORIGINS=https://buildsafe-ai.vercel.app,https://some-ngrok-url.ngrok-free.dev
```

For Heroku, Render, Railway, or similar platforms, configure these environment variables in the hosting dashboard:

- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `GEMINI_ENABLED`
- `FRONTEND_ORIGINS`
- `DEBUG_TRACE_ENABLED` if you need local-style debug traces

The included [`Procfile`](Procfile) runs:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Deploy On Heroku

Use Heroku for the FastAPI backend. The backend has the required pieces for Heroku-style deployment:

- [requirements.txt](requirements.txt) with `fastapi`, `uvicorn`, `python-dotenv`, and `httpx`
- [Procfile](Procfile) with `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Create the Heroku app:

```bash
heroku create YOUR-HEROKU-BACKEND
```

Set config vars:

```bash
heroku config:set GEMINI_API_KEY=your_key_here
heroku config:set GEMINI_MODEL=gemini-flash-latest
heroku config:set GEMINI_ENABLED=true
heroku config:set FRONTEND_ORIGINS=https://YOUR-VERCEL-FRONTEND.vercel.app
```

Do not include a trailing slash in `FRONTEND_ORIGINS`; it must be the exact browser origin.

Deploy the backend. If your Git remote root is `buildsafe-ai`, push only the backend folder to Heroku:

```bash
git subtree push --prefix backend heroku main
```

If your Git remote root is already `buildsafe-ai/backend`, deploy normally:

```bash
git push heroku main
```

Test the deployed backend:

```text
https://YOUR-HEROKU-BACKEND.herokuapp.com/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "BuildSafe AI Backend"
}
```

## Run The Smoke Tests

```bash
cd buildsafe-ai/backend
python -m unittest discover -s tests -v
```

The smoke suite includes [tests/test_demo_cases.py](tests/test_demo_cases.py) for the seven supervisor demo scenarios and [tests/test_update_assessment.py](tests/test_update_assessment.py) for update parsing, reassessment, and changed-vs-unchanged summaries.

## Key Endpoints

- `GET /health`: health check
- `POST /api/llm/plan-followups`: task-intent detection plus up to 2 safety-critical follow-up questions
- `POST /api/assess-task`: final assessment with explainable score, warnings, tools, PPE, and professional recommendation
- `POST /api/update-assessment`: parse a new message against an existing completed assessment, merge changed context, rerun the risk engine, and return changed/unchanged sections
- `GET /api/admin/seed-data`: read-only MVP seed data

## Backend Safety Model

`task_intent`

- The backend resolves ambiguous natural-language tasks into a concrete intent such as `hanging_wall_decor`, `wall_painting`, `ceiling_fan_installation`, `wall_demolition`, or `plumbing_leak_repair`.

Rule engine

- The rule engine is the final authority.
- It combines task keywords, category priors, follow-up answers, and explicit safety rules.
- It also keeps high-risk tasks conservative, especially around structure, gas, water, and electricity.

Gemini augmentation

- Gemini can assist with follow-up planning, interpretation, and explanation language.
- Gemini can also parse natural-language update messages when enabled.
- If Gemini is unavailable, fallback rules detect common changes such as weight, wall material, attachment method, hidden utilities, tools, skill level, and damaged electrical items.
- Gemini does not directly decide the final risk level.

Recommendation consistency

- The backend cleans recommendation mismatches for ambiguous phrasing.
- Example: "hang a painting" must not return paint rollers, brushes, trays, wall paint, or drying-time language.

## Explainable Risk Score Rubric

The backend now returns `risk_score_breakdown` with:

- `base_task_risk`: `0-30`
- `hazard_severity`: `0-25`
- `skill_mismatch`: `0-15`
- `tools_ppe_readiness`: `0-15`
- `environment_urgency_unknowns`: `0-15`
- `total`: final score out of `100`
- `threshold_label`: rubric-based tier before overrides
- `safety_overrides_applied`: any hard safety escalations

Risk thresholds:

- `0-20`: Safe DIY
- `21-40`: DIY with supervision
- `41-60`: Professional recommended
- `61-80`: Professional required
- `81-100`: Dangerous / permit-required / do not attempt

Safety overrides can lift the final risk tier above the threshold label for hazardous triggers such as:

- gas line work
- main electrical panel work
- exposed wiring
- load-bearing uncertainty
- structural demolition
- roof work at height
- water leakage near electricity
- unknown hidden utilities during demolition or drilling

## Update Assessment Behavior

`POST /api/update-assessment` is used after a final assessment already exists. It accepts the previous assessment, previous answers/context, and a new `update_message`.

The endpoint returns:

- `updated_assessment`
- `change_summary.detected_updates`
- `change_summary.changed_sections`
- `change_summary.unchanged_sections`
- risk score and risk level comparison
- `debug_trace` showing whether Gemini or fallback parsing was used

The update flow is impact-aware. For example, changing a painting from `1 kg` to `2 kg` may update risk score, materials, and safety warnings while preserving task intent, task category, and basic tools. Hidden wiring, exposed wires, gas, structural uncertainty, and water near electricity are reassessed conservatively.

## Supervisor Demo Scenario Matrix

| Scenario | What the backend should show |
| --- | --- |
| hang a new painting in my bedroom | `hanging_wall_decor`, wall-decor questions, no paint tools, low-risk output |
| paint my bedroom | `wall_painting`, roller/brush/tray, paint/primer, drying time |
| hang a heavy mirror on a tiled bathroom wall | still wall decor, no paint tools, higher risk than lightweight decor, anchor guidance |
| install a ceiling fan | electrical category, voltage tester + insulated tools, electrician recommendation |
| break a wall between rooms | demolition/structural caution, professional-only stance |
| replace a light bulb | 0-1 follow-up question, no budget question, simple low-risk path |
| fix a leaking pipe | asks about visible vs hidden leak and nearby electrical risk |

## Example Curl Requests

Plan follow-ups:

```bash
curl -X POST http://localhost:8000/api/llm/plan-followups ^
  -H "Content-Type: application/json" ^
  -d "{\"task_description\":\"I want to hang a new painting in my bedroom.\",\"known_answers\":{}}"
```

Assess a task:

```bash
curl -X POST http://localhost:8000/api/assess-task ^
  -H "Content-Type: application/json" ^
  -d "{\"task_description\":\"I want to install a ceiling fan.\",\"user_skill_level\":\"beginner\",\"available_tools\":[\"voltage tester\",\"insulated screwdriver\",\"stable ladder\"],\"location_type\":\"house\",\"urgency\":\"low\",\"budget_range\":\"not specified\",\"answers_to_followups\":{\"Is there existing wiring and a fan-rated ceiling box already in place?\":\"yes\",\"What is your skill level with electrical work: beginner, intermediate, or expert?\":\"beginner\"}}"
```

Update a completed assessment:

```bash
curl -X POST http://localhost:8000/api/update-assessment ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"demo-session-1\",\"previous_assessment\":{\"risk_score\":28,\"risk_level\":\"Safe DIY\",\"recommended_tools\":[\"measuring tape\",\"level\",\"drill\"],\"recommended_materials\":[\"wall anchors\",\"screws\"],\"ppe\":[\"safety glasses\"],\"safety_warnings\":[],\"professional_recommendation\":\"Not required for a lightweight item if the wall condition is known.\"},\"task_description\":\"I want to hang a new painting in my bedroom.\",\"task_intent\":\"hanging_wall_decor\",\"task_category\":\"home_improvement\",\"previous_answers\":{\"weight\":\"1 kg\",\"attachment_method\":\"drilling\"},\"update_message\":\"Actually, it weighs 2 kg.\",\"current_user_context\":{\"user_skill_level\":\"beginner\",\"available_tools\":[\"measuring tape\",\"level\",\"drill\"],\"location_type\":\"bedroom\",\"urgency\":\"low\",\"budget_range\":\"not specified\"}}"
```

## Known Limitations

- The backend uses heuristic task-intent and rule mappings rather than a trained production classifier.
- Recommendations are seed-data driven and not yet connected to products, pricing, or availability.
- No photo, document, or worksite image analysis is implemented yet.
- Hidden conditions still depend on the quality of user-provided answers.

## Future Work

- RAG-based hardware and tool database
- Product recommendations with brand and price
- Professional marketplace integration
- Quote request workflow
- Image and photo upload
- PostgreSQL migration
- ML classifier training
