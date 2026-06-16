# BuildSafe AI / ConstructMate

Safety-first DIY and construction task assessment prototype for a Computer Science Final Year Project.

For repository-wide product and development rules, see [PROJECT_INSTRUCTIONS.md](PROJECT_INSTRUCTIONS.md).

## Stack

- Backend: FastAPI, Python, JSON seed data
- Frontend: React, Vite, Tailwind CSS
- Future database target: PostgreSQL

## Run

Backend:

```bash
cd buildsafe-ai/backend
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

## Demo Flow

1. Enter a task such as `install a ceiling fan`.
2. Select skill level, location type, urgency, available tools, and budget.
3. Submit the task.
4. Review the risk decision, reasoning, tools, materials, PPE, professional recommendation, time/cost estimate, and follow-up questions.
5. Scroll to Admin Seed Data to show the rule and catalog data powering the MVP.

## Roadmap

- ML classifier integration for task category and baseline risk prediction.
- PostgreSQL migration for rules, catalogs, assessments, and professionals.
- Quote request system for professional-recommended tasks.
- Professional marketplace for verified trade matching.
- Photo upload and computer-vision-assisted hazard detection.
