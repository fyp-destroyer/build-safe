# BuildSafe AI Project Instructions

This repository is for a Computer Science Final Year Project called BuildSafe AI / ConstructMate.

The product is a risk-aware DIY and construction task assessment platform. It should not be treated as a generic chatbot.

## Core Principle

The system should first decide whether a user should attempt a DIY or construction task at all.

## Risk Levels

1. Safe DIY
2. DIY with supervision
3. Professional recommended
4. Professional required
5. Dangerous / permit-required / do not attempt

## Development Rules

- Keep the system safety-first.
- Do not generate unsafe step-by-step instructions for dangerous electrical, structural, gas, roofing, or demolition tasks.
- Use the risk engine as the authority for the final decision.
- The LLM/chat layer, if added later, should only explain the decision and ask follow-up questions.
- Keep backend logic modular.
- Keep frontend UI professional and supervisor-demo ready.
- Prefer readable code over over-engineered code.
- Add comments for future ML, database, and marketplace integration.
- Update README files whenever major changes are made.

## Recommended Architecture

- Frontend: React or Next.js
- Backend: FastAPI
- Database: SQLite or JSON for MVP, PostgreSQL later
- AI: rule-based MVP, ML classifier later
- Future modules: quote requests, professional marketplace, admin dashboard, photo upload
