# BuildSafe AI Frontend

React + Vite + Tailwind prototype for the BuildSafe AI risk assessment and construction safety triage interface.

## Run Locally

Start the backend first on port `8000`.

```bash
cd buildsafe-ai/frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

Optional API override:

```bash
set VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

## Build

```bash
npm run build
```

## Demo Features

- Task intake form with validation for task description and tool count.
- Structured risk report sections: Decision, Why this is risky/safe, Required tools, Required materials, PPE checklist, Professional recommendation, Estimated time and cost, and Follow-up questions.
- Risk-level badges with distinct colors for supervisor-friendly scanning.
- Admin Seed Data panel that reads `GET /api/admin/seed-data` and displays tools, materials, safety rules, and professional categories in a read-only JSON editor placeholder.
- Error handling for API failures and backend validation responses.

## Sample Demo Tasks

- `paint a room`
- `replace air filter`
- `install tiles on kitchen backsplash`
- `fix leaking pipe under sink`
- `paint exterior high wall`
- `mount tv on drywall`
- `install a ceiling fan`
- `install ac unit`
- `break a wall between two rooms`
- `repair main electrical panel`
- `fix gas line leak`

## Roadmap TODOs

- Add photo upload to attach job-site images to an assessment.
- Add quote request flow after Professional recommended or higher decisions.
- Add a professional marketplace view for trade categories and provider matching.
- Add an admin editor backed by PostgreSQL instead of read-only JSON seed files.
