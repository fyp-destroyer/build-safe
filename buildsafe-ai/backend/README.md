# BuildSafe AI Backend

FastAPI backend for risk-aware DIY and construction task assessment.

## Run Locally

```bash
cd buildsafe-ai/backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

Assess a task:

```bash
curl -X POST http://localhost:8000/api/assess-task ^
  -H "Content-Type: application/json" ^
  -d "{\"task_description\":\"install a ceiling fan\",\"user_skill_level\":\"beginner\",\"available_tools\":[\"drill\",\"ladder\"],\"location_type\":\"house\",\"urgency\":\"medium\",\"budget_range\":\"$50-$100\",\"answers_to_followups\":{}}"
```

## Sample Test Tasks

- `paint a room`
- `install a shelf in a bedroom`
- `fix leaking pipe under sink`
- `install a ceiling fan`
- `repair wiring near an outlet`
- `break a wall between two rooms`
- `repair main electrical panel`
- `fix gas line leak`

## MVP Logic

The current risk engine is rule-based and reads seed rules from `app/data/safety_rules.json`.
The code includes a future ML integration point in `app/services/risk_engine.py`, where a trained classifier can later provide task category and risk priors before safety rules apply guardrails.
