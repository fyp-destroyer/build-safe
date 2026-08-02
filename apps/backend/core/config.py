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
    # How long a session lasts. Was effectively 60 minutes, which logged the
    # user out mid-use and — because the frontend only checked that a token
    # EXISTED — left the app looking signed in while every request 401'd.
    # 30 days, plus the sliding renewal in core/security.py, is what makes
    # "open it and you're still logged in" true in practice.
    #
    # The trade-off, stated plainly: a long-lived token in localStorage is
    # valid for its full lifetime if stolen, and there is no revocation list.
    # Acceptable for this app (single `user` role, no payment or PII beyond
    # an email); revisit before any real deployment — the fix is short-lived
    # access tokens plus a refresh token in an httpOnly cookie.
    JWT_EXPIRES_MINUTES: int = 60 * 24 * 30
    ENV: str = "development"

    # Browser origins allowed to call this API, comma-separated. Never a
    # wildcard: credentials (the Authorization bearer header) are involved,
    # and `allow_credentials=True` with `*` is rejected by browsers anyway.
    #
    # Made configurable 2026-08-01 — the dev port was hardcoded here, so
    # moving the frontend off :3000 silently broke every request at the CORS
    # preflight rather than anywhere that looked like the cause.
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

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

    # --- Risk pipeline ----------------------------------------------------
    # Whether the ML classifier's prediction takes part in
    # `final_risk = max(ml_risk, rule_risk)`.
    #
    # Default TRUE: that max() is the documented, non-negotiable flow
    # (architecture.md §2, srs.md §8.1 NFR-03, CLAUDE.md), and the default
    # must be the documented behaviour.
    #
    # Set FALSE to run rules-only. Turned off in dev on 2026-08-01 at the
    # user's decision, because the shipped classifier is currently a near-
    # constant function of `user_skill` rather than of the task: 77 of the 85
    # `Experienced` rows in the training data are level 4, so it returns 4 for
    # an Experienced user on a light bulb, a paint roller and a flat-pack
    # wardrobe alike, while returning 1 for a Beginner on "rewire the consumer
    # unit". See `ml/analyze_skill_bias.py` for the measurement and memory.md
    # for the decision.
    #
    # WHAT THIS COSTS, STATED PLAINLY: dropping a term from a max() can only
    # LOWER the result. A task that matches no keyword and receives no LLM
    # hazard tag now returns level 1 with nothing to catch it — the rule
    # engine's known blind spot, for which the classifier was nominally the
    # cover. That cover is presently fictional (see above), which is why this
    # is defensible, but it is a real reduction in coverage and not a
    # cost-free simplification.
    #
    # The classifier still RUNS and its prediction is still written to
    # `ai_logs.model_output` when this is off — only its contribution to the
    # decision is suppressed. Nothing is hidden; flip this back to true and
    # the documented pipeline returns unchanged.
    RISK_USE_ML_CLASSIFIER: bool = True


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — import this, not Settings() directly."""
    return Settings()
