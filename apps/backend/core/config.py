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
    ENV: str = "development"

    # --- LLM provider ---------------------------------------------------
    # Two interchangeable providers; both are used only for the narrow,
    # schema-constrained jobs allowed by rules.md §4 (category tagging,
    # hazard tagging against the closed catalog, follow-up phrasing), and
    # neither can ever produce a risk level. Swapping provider therefore
    # cannot change what the system decides — only its wording and tagging
    # quality. See ai/llm/client.py.
    #
    # LLM_PROVIDER: "gemini" | "groq" | "auto" (default). "auto" picks
    # whichever key is configured, preferring Gemini when both are, so
    # adding a Groq key never silently changes an existing setup — set
    # LLM_PROVIDER=groq explicitly to switch.
    LLM_PROVIDER: str = "auto"
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    # Overridable so a model retirement is a config change, not a code
    # change — the Gemini side already got caught by exactly that (see the
    # _MODEL_NAME note in ai/llm/client.py).
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"
    GROQ_MODEL: str = "llama-3.3-70b-versatile"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — import this, not Settings() directly."""
    return Settings()
