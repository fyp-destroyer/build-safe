"""Shared pytest fixtures.

Uses a real Postgres instance for tests (async SQLAlchemy requires an async
driver; `aiosqlite` was not installable in this environment — no network
access to PyPI — so tests run against Postgres instead, per the task's
"if Postgres isn't reasonably available... use SQLite" fallback guidance,
inverted: Postgres *is* available here via docker-compose, so it's used
directly rather than adding a same-purpose SQLite driver).

Set TEST_DATABASE_URL to override the default, which targets a disposable
Postgres container on port 5433 (kept separate from the docker-compose
`buildsafe-postgres` dev container on 5432 so tests never touch dev data):

    docker run -d --name buildsafe-postgres-test \\
      -e POSTGRES_USER=buildsafe -e POSTGRES_PASSWORD=buildsafe \\
      -e POSTGRES_DB=buildsafe_test -p 5433:5432 pgvector/pgvector:pg16

Each test function runs inside a transaction that is rolled back afterward,
so tests never leak state into each other.
"""

import os
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://buildsafe:buildsafe@127.0.0.1:5433/buildsafe_test",
)

from core.db import get_db  # noqa: E402
from main import app  # noqa: E402
from models import Base  # noqa: E402

engine = create_async_engine(TEST_DATABASE_URL)
TestSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _documented_risk_pipeline(monkeypatch):
    """Pin `RISK_USE_ML_CLASSIFIER` on for every test that doesn't opt out.

    `Settings` reads `apps/backend/.env`, and pytest runs from that
    directory, so a developer's local `.env` silently becomes test
    configuration. That is exactly what happened when rules-only mode was
    switched on in dev (2026-08-01): `test_classifier_exception_writes_
    failed_assessment_and_ai_log` flipped to green-but-meaningless, because
    a classifier crash genuinely does not fail an assessment the classifier
    is not part of. The suite must assert the DOCUMENTED pipeline
    (`final_risk = max(ml, rules)`) regardless of how any one machine is
    configured; rules-only mode gets its own explicit tests instead.

    Use `set_risk_pipeline(monkeypatch, use_ml=False)` to opt out.
    """
    from core.config import get_settings

    set_risk_pipeline(monkeypatch, use_ml=True)
    yield
    # Drop the cache again so the value this test forced cannot leak into
    # the next one — monkeypatch restores the env var, not the lru_cache.
    get_settings.cache_clear()


def set_risk_pipeline(monkeypatch, *, use_ml: bool) -> None:
    """Force RISK_USE_ML_CLASSIFIER for one test.

    `get_settings` is `lru_cache`d, so setting the environment variable is
    not enough on its own — the cache has to be dropped, or whichever test
    touches settings first fixes the value for the entire session.
    """
    from core.config import get_settings

    monkeypatch.setenv("RISK_USE_ML_CLASSIFIER", "true" if use_ml else "false")
    get_settings.cache_clear()


@pytest.fixture(scope="session")
async def _create_schema():
    """Create all tables once for the test session, drop at the end.

    Uses Base.metadata directly for test speed/isolation rather than
    running Alembic migrations in the loop — the migration itself is
    verified separately (see report: `alembic upgrade head` was run
    against this same test database as part of implementation).

    NOT autouse on purpose: the safety-critical rule-engine and classifier
    tests are pure logic and must stay runnable without a database
    container. Only fixtures that genuinely touch the DB request this.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(_create_schema):
    """A DB session wrapped in a transaction that's rolled back after the
    test, so tests never see each other's data."""
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


@pytest.fixture
async def client(db_session):
    """An httpx AsyncClient wired to the FastAPI app with get_db overridden
    to use the per-test rolled-back session."""

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def register_and_login(client: AsyncClient, email: str, password: str = "password123") -> str:
    """Helper: register a user and return their bearer token."""
    resp = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "name": "Test User"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]
