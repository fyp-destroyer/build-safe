"""SQLAlchemy async engine + session factory.

Phase 0: wiring only, not exercised by any route yet (GET /health does not
touch the DB, intentionally, so it works without Postgres running).
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, echo=settings.ENV == "development")

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a scoped async session. Not wired into any
    router yet — models/services land in later phases."""
    async with AsyncSessionLocal() as session:
        yield session
