# BuildSafe AI Backend

FastAPI backend for a safety-first DIY and construction task assessment platform.

## Run Locally

```bash
cd buildsafe-ai/backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open the API docs:

```text
http://localhost:8000/docs
```

## Endpoints

- `GET /health` returns service health.
- `POST /api/assess-task` returns the risk report payload.
- `GET /api/admin/seed-data` returns read-only MVP seed data for the frontend admin placeholder.

## Assess a Task

```bash
curl -X POST http://localhost:8000/api/assess-task ^
  -H "Content-Type: application/json" ^
  -d "{\"task_description\":\"install a ceiling fan\",\"user_skill_level\":\"beginner\",\"available_tools\":[\"drill\",\"ladder\"],\"location_type\":\"house\",\"urgency\":\"medium\",\"budget_range\":\"$50-$100\",\"answers_to_followups\":{}}"
```

## Demo Task Matrix

These examples use the listed skill and urgency values with empty follow-up answers.

| Task | Skill | Urgency | Expected risk |
| --- | --- | --- | --- |
| paint a room | beginner | low | Safe DIY |
| install a shelf in a bedroom | beginner | low | Safe DIY |
| replace air filter | beginner | low | Safe DIY |
| install tiles on kitchen backsplash | intermediate | medium | DIY with supervision |
| fix leaking pipe under sink | beginner | medium | Professional recommended |
| paint exterior high wall | beginner | high | Professional recommended |
| mount tv on drywall | beginner | medium | Professional recommended |
| install a ceiling fan | beginner | medium | Professional required |
| install ac unit | intermediate | high | Dangerous / permit-required / do not attempt |
| break a wall between two rooms | intermediate | high | Dangerous / permit-required / do not attempt |
| repair main electrical panel | expert | high | Dangerous / permit-required / do not attempt |
| fix gas line leak | expert | emergency | Dangerous / permit-required / do not attempt |

## MVP Logic

The current risk engine is rule-based and reads seed rules from `app/data/safety_rules.json`.
Categories covered include electrical, plumbing, masonry/demolition, painting, carpentry, tiling, HVAC, roofing, gas, structural, and general DIY.

Input validation is handled through Pydantic enums and field validators. Invalid assessment payloads return:

```json
{
  "message": "Invalid assessment input",
  "details": []
}
```

## Roadmap TODOs

- ML classifier integration: replace or enhance keyword rules with a trained task classifier while keeping safety rules as guardrails.
- PostgreSQL migration: move JSON seed files into normalized tables for categories, rules, tools, materials, PPE, and professional mappings.
- Quote request system: create quote request records from high-risk assessments.
- Professional marketplace: match users with verified electricians, plumbers, HVAC technicians, contractors, and engineers.
- Photo upload: accept job-site images and extract visible hazard signals for the risk engine.
