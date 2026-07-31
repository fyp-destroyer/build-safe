"""Gemini client wrapper.

**THIS IS THE ONLY MODULE IN THE ENTIRE CODEBASE THAT CALLS AN LLM.** Every
other module that needs an LLM-assisted answer must go through
`generate_structured` below — never instantiate `google.genai.Client`
anywhere else.

Boundary (rules.md §4 / CLAUDE.md, non-negotiable):
  - The LLM is template/schema-constrained only. `generate_structured` forces
    Gemini into structured JSON output matching a caller-supplied Pydantic
    schema (`response_mime_type="application/json"` + `response_schema`) —
    it is never allowed to return free text that gets trusted as-is.
  - The LLM is NEVER used to emit a risk level, invent a hazard rule, or
    invent a category outside a fixed, code-reviewed closed set. Its only
    permitted jobs anywhere in this codebase are: (a) phrasing follow-up
    question text for an already-hardcoded field, (b) turning already-
    triggered rules into templated explanation text, and (c) tagging which
    member of a fixed category/rule set a task's text matches. See
    `ai/rule_engine/llm_assist.py` for the only caller of this module.
  - This function never raises. Any failure (network error, missing/invalid
    API key, timeout, rate limit, malformed/unparseable response) is caught,
    logged as a warning, and surfaced as `None`. Every caller MUST treat
    `None` as "LLM unavailable" and fall back to a hardcoded, safe default —
    this module succeeding is never load-bearing for safety, only for
    wording/tagging convenience (rules.md §2 fail-loud philosophy: the
    *fallback path*, not this function, is what must remain safe).
"""

import logging
import os
from functools import lru_cache
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from core.config import get_settings

logger = logging.getLogger(__name__)

# Small, fast, current Gemini model — appropriate for low-latency structured
# classification/phrasing calls (not long-form generation).
# Overridable so a model retirement is a config change, not a code change.
#
# NOT gemini-2.5-flash: it still appears in models.list() but generateContent
# rejects it for keys created after its retirement ("no longer available to
# new users", HTTP 404), so the whole LLM layer silently fell back to its
# hardcoded defaults. Found only by reading the actual API error - the
# fallbacks are so well-behaved that nothing looked broken from outside.
_MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

ModelT = TypeVar("ModelT", bound=BaseModel)


@lru_cache
def _get_client() -> genai.Client | None:
    """Lazily build a cached Gemini client, or None if no API key is set.

    Cached so we don't reconstruct the client on every call; a missing key
    (e.g. in tests/CI, which never call this module directly — they
    monkeypatch `generate_structured` instead) is a normal, expected state,
    not an error.
    """
    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        return None
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def generate_structured(prompt: str, response_schema: type[ModelT]) -> ModelT | None:
    """Call Gemini with a prompt, constrained to emit JSON matching
    `response_schema`, and return a validated instance of that schema.

    Returns None (never raises) if: the API key isn't configured, the
    network call fails for any reason, or the response can't be validated
    against `response_schema`. Callers must always have a hardcoded fallback
    for the None case.
    """
    client = _get_client()
    if client is None:
        logger.warning("Gemini client unavailable (no GEMINI_API_KEY); returning None.")
        return None

    try:
        response = client.models.generate_content(
            model=_MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
            ),
        )
    except Exception:  # noqa: BLE001 - must never raise out of this function
        logger.warning("Gemini API call failed; caller must use its hardcoded fallback.")
        return None

    parsed = response.parsed
    if isinstance(parsed, response_schema):
        return parsed

    # Defense in depth: the SDK didn't hand back an already-validated
    # instance (e.g. it fell back to a raw dict/None). Try validating the
    # raw response text ourselves before giving up.
    try:
        return response_schema.model_validate_json(response.text)
    except (ValidationError, ValueError, TypeError, AttributeError):
        logger.warning("Gemini response failed schema validation; returning None.")
        return None
