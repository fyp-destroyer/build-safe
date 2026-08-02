# infra

There is no infrastructure to run.

That is the point of this directory now. BuildSafe AI used to need a local
Postgres + pgvector container (`docker-compose.yml`), Alembic migrations, and a
separate Python API process. All of it is gone: the backend moved to Convex,
which is a hosted database and function runtime, and auth moved to Clerk.

Nothing is self-hosted, so there is nothing here to configure.

## What runs where

| Concern | Service | Configured in |
| --- | --- | --- |
| Frontend (Next.js) | Vercel | `apps/frontend/vercel.json` |
| Database + backend functions | Convex | `apps/frontend/convex/` |
| Authentication | Clerk | `apps/frontend/convex/auth.config.ts`, `apps/frontend/proxy.ts` |

## Local development

Two processes, no Docker, no database:

```bash
cd apps/frontend
npx convex dev     # watches convex/ and pushes to the dev deployment
npm run dev        # Next.js on http://localhost:3000
```

`npx convex dev` writes `CONVEX_DEPLOYMENT` and `NEXT_PUBLIC_CONVEX_URL` into
`.env.local` on first run.

## Environment variables

Secrets used by backend logic live in the **Convex dashboard**, not in Vercel and
never in a `NEXT_PUBLIC_` variable — Convex functions read them at runtime, and
anything prefixed `NEXT_PUBLIC_` is shipped to the browser.

**Convex → Settings → Environment Variables**

```
CLERK_JWT_ISSUER_DOMAIN     https://<your-app>.clerk.accounts.dev
CLERK_WEBHOOK_SECRET        whsec_...        (Clerk → Webhooks → signing secret)
GEMINI_API_KEY              ...              (optional if GROQ_API_KEY is set)
GROQ_API_KEY                ...              (optional if GEMINI_API_KEY is set)
LLM_PROVIDER                auto | gemini | groq
RISK_USE_ML_CLASSIFIER      true             (the documented max(ML, rules) pipeline)
```

**Vercel → Project → Environment Variables**

```
NEXT_PUBLIC_CONVEX_URL                  https://<deployment>.convex.cloud
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY       pk_...
CLERK_SECRET_KEY                        sk_...
NEXT_PUBLIC_CLERK_SIGN_IN_URL           /login
NEXT_PUBLIC_CLERK_SIGN_UP_URL           /register
NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL   /chat
NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL   /chat
```

Also set **Root Directory = `apps/frontend`** in Vercel's Build & Deployment
settings. The repository has no root `package.json`, so a build from the repo
root fails before it starts.

### Deploying against the DEV Convex deployment (current setup)

`vercel.json` runs a plain `npm run build`. It deliberately does **not** run
`convex deploy`, because that would create and push to a *production* Convex
deployment; this project is intentionally still running everything against dev.

The consequence is worth stating plainly: Vercel serves the frontend, but the
backend it talks to is the dev deployment named in `NEXT_PUBLIC_CONVEX_URL`.
Whatever `npx convex dev` last pushed is what the deployed site runs, so a local
edit to `convex/` changes the live site. Fine for a demo, wrong for anything with
real users.

### Switching to production later

Three changes, in this order:

1. Set `buildCommand` in `vercel.json` to `npx convex deploy --cmd 'npm run build'`.
2. Add `CONVEX_DEPLOY_KEY` in Vercel (Convex → Settings → Deploy Keys → generate a
   **production** key). This is what authenticates `convex deploy` in CI.
3. **Remove** `NEXT_PUBLIC_CONVEX_URL` from Vercel — `convex deploy` injects the
   production URL itself, and a manually-set value would pin the production site
   to the dev backend.

Then re-add every Convex environment variable to the production deployment: dev
and prod are separate and share nothing, so a fresh production deployment starts
with no `CLERK_JWT_ISSUER_DOMAIN`, no webhook secret and no LLM key, and will
fail in ways that look like code bugs.

## Clerk webhook

Point Clerk at the deployment's **`.convex.site`** domain — HTTP actions are not
served from `.convex.cloud`, and using the wrong one 404s:

```
https://<your-deployment>.convex.site/clerk-webhook
```

Subscribe to `user.created`, `user.updated`, `user.deleted`. The webhook keeps
the local `users` row in step and, on deletion, removes that user's jobs,
transcripts, assessments and AI logs. Account creation does not depend on it —
`users.getOrCreateCurrent` creates the row just-in-time on first use.

## What happened to pgvector

The extension was enabled for a planned semantic tool/material retrieval layer
that was never built — no vector column, no embeddings, no queries. It is not
carried over. If that feature is ever picked up, Convex has its own vector
indexes and would not need this directory back.
