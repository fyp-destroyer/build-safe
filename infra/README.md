# infra

Local infrastructure for BuildSafe AI. Currently this is just the Postgres +
pgvector database defined in the root `docker-compose.yml`; the
`postgres-initdb/` folder holds the SQL that runs on first container init to
enable the `vector` extension.

## Start Postgres locally

```
docker compose up -d
```

This starts a single `postgres` service (image `pgvector/pgvector:pg16`) on
`localhost:5432` with user/password/db all `buildsafe`, backed by a named
volume so data survives restarts.

## Verify pgvector is enabled

```
docker compose exec postgres psql -U buildsafe -d buildsafe -c "SELECT * FROM pg_extension;"
```

You should see a `vector` row in the output. To stop the database:

```
docker compose down
```

(add `-v` to also drop the data volume).

## Deployment configs (Phase 8)

Deployment configuration — Vercel for the frontend, Render/Railway/Fly.io for
the backend, and a managed Postgres provider for the database — will live in
this directory as it's added in Phase 8.
