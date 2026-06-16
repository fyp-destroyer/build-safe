# BuildSafe AI Frontend

React + Vite + Tailwind prototype for the BuildSafe AI safety triage interface.

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

## Sample Demo Tasks

- `paint a room`
- `install a shelf`
- `fix leaking pipe`
- `install a ceiling fan`
- `repair wiring`
- `break a wall`
- `repair main electrical panel`
- `fix gas line leak`
