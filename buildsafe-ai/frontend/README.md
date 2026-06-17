# BuildSafe AI Frontend

This frontend is the chat-based supervisor demo for BuildSafe AI / ConstructMate. It sends the user task to the backend, shows short follow-up questions, renders the final structured risk card, and can optionally expose the Developer Trace panel for Gemini and rule-engine visibility.

After a completed assessment, the frontend also keeps an active assessment session so the user can update details in the same chat without restarting the full assessment flow.

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

## Frontend Environment

Use [`.env.example`](.env.example) for local configuration:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_SHOW_DEBUG_PANEL=false
```

Developer Trace rules:

- Set `VITE_SHOW_DEBUG_PANEL=true` to show the Developer Trace section in local development.
- The panel is hidden in production builds even if the flag is set.
- The backend must also set `DEBUG_TRACE_ENABLED=true` for debug data to actually appear.

## Build

```bash
npm run build
```

## What The UI Demonstrates

- Chat-style task submission
- Maximum 1-2 follow-up questions before the final assessment
- Typewriter-style explanation copy
- Structured risk card inside the chat
- "Why this score?" collapsible panel for rubric explainability
- Risk score breakdown with points and reasons
- Safety override visibility
- Active assessment session state after the final card is shown
- Same-chat assessment updates through `POST /api/update-assessment`
- `What changed?` and `What stayed the same?` summary cards
- Outdated action-plan warning when risk-relevant information changes
- Optional LLM-assisted Developer Trace panel

## Frontend Demo Flow

1. User enters a task.
2. Frontend calls `POST /api/llm/plan-followups`.
3. The assistant asks up to 2 crucial safety questions.
4. Frontend calls `POST /api/assess-task`.
5. The result card shows:
   - final risk level
   - risk score out of 100
   - explainable score breakdown
   - warnings
   - tools, materials, PPE
   - professional recommendation
   - optional Developer Trace
6. Frontend stores an `activeAssessmentSession` containing the original task, task intent, follow-up answers, latest assessment, assessment history, and action plan status.
7. If the user types another message after the final card, the frontend treats it as a possible update and calls `POST /api/update-assessment`.
8. The chat displays the updated risk card plus changed/unchanged sections. Starting a new assessment clears the previous session.

## Update Assessment Demo Flow

Use this flow to show the feature to a supervisor:

1. Enter `I want to hang a new painting in my bedroom.`
2. Answer the follow-up with `It weighs 1 kg and I will drill.`
3. Show the final risk card.
4. Generate an action plan if the button is available.
5. Type `Actually, it weighs 2 kg.`
6. Show that the chat updates the same assessment instead of asking all questions again.
7. Point out `What changed?`, `What stayed the same?`, assessment history, and any outdated-plan warning.

When the update is minor, the plan may remain active. When the update changes risk level, raises the risk score significantly, changes warnings, changes professional recommendation, or changes the required method/materials, the old plan is marked outdated and the button becomes `Regenerate Plan`.

## Recommended Demo Prompts

- `I want to hang a new painting in my bedroom.`
- `I want to paint my bedroom.`
- `I want to hang a heavy mirror on a tiled bathroom wall.`
- `I want to install a ceiling fan.`
- `I want to break a wall between my kitchen and living room.`
- `I want to replace a light bulb.`
- `I want to fix a leaking pipe.`

Follow-up update prompts after a completed assessment:

- `Actually, it weighs 2 kg.`
- `Actually, it is 8 kg.`
- `The wall is concrete.`
- `I will use adhesive strips instead of drilling.`
- `There may be electrical wiring behind the wall.`
- `The holder is damaged and I can see wires.`

## What To Point Out During The Pitch

- The chat stays short and safety-focused instead of feeling like a generic chatbot.
- Ambiguous phrases such as "painting" are separated into framed wall decor versus room painting.
- The risk score is no longer a black box because the rubric is visible on the card.
- Safety overrides are explicitly shown when the final tier is more conservative than the numeric threshold.
- The update flow is impact-aware: changing one detail updates relevant sections without changing the whole task.
- Old action plans are not blindly reused after important safety assumptions change.
- The LLM-assisted label and Developer Trace make Gemini involvement visible without removing deterministic control.

## Known Limitations

- The UI depends on backend seed data and does not yet connect to real products or service providers.
- The current demo is text-first and does not yet support image upload or photo analysis.
- The Developer Trace panel is for local demos and debugging, not end-user production display.
