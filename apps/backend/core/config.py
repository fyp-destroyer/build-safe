"""Application settings, loaded from environment / .env.

Phase 0: just the settings object. Nothing imports/uses this at startup yet
so /health has no dependency on env vars being present.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed environment configuration.

    See .env.example for the expected keys. Values are placeholders in dev;
    real secrets are never committed.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://buildsafe:buildsafe@localhost:5432/buildsafe"
    JWT_SECRET: str = "changeme"
    GEMINI_API_KEY: str = ""
    ENV: str = "development"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — import this, not Settings() directly."""
    return Settings()
