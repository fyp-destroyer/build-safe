-- Runs automatically on first container init (docker-entrypoint-initdb.d).
-- Enables the pgvector extension so BuildSafe AI's semantic
-- tool/material/task retrieval (architecture.md) works out of the box.
CREATE EXTENSION IF NOT EXISTS vector;
