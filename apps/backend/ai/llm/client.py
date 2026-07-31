"""LLM client wrapper — Gemini or Groq, behind one function.

**THIS IS THE ONLY MODULE IN THE ENTIRE CODEBASE THAT CALLS AN LLM.** Every
other module that needs an LLM-assisted answer must go through
`generate_structured` below — never instantiate a provider client anywhere
else.

Boundary (rules.md §4 / CLAUDE.md, non-negotiable):
  - The LLM is template/schema-constrained only. `generate_structured` forces
    the model into structured JSON output matching a caller-supplied Pydantic
    schema — it is never allowed to return free text that gets trusted as-is.
    Whatever comes back is validated against that schema before any caller
    sees it, on every provider.
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

CHOOSING A PROVIDER
-------------------
`LLM_PROVIDER` = "gemini" | "groq" | "auto" (default), with `GEMINI_API_KEY`
/ `GROQ_API_KEY` supplying credentials. "auto" uses whichever key is set and
prefers Gemini when both are, so adding a Groq key never silently changes an
existing setup — set `LLM_PROVIDER=groq` to actually switch.

Because both providers are confined to the schema-constrained jobs listed
above, and every reply is validated against a Pydantic schema before use,
which provider is configured cannot change any risk decision. A weaker model
degrades tagging/wording quality, and an invalid reply degrades to the same
`None` (hardcoded fallback) path as an outage. Neither can escalate,
de-escalate, or invent a rule — that arithmetic lives entirely in
`ai/rule_engine/` and never consults this module.

Run `python scripts/check_llm.py` to confirm the configured provider and
model actually answer, and in which JSON mode.
"""

import json
import logging
from functools import lru_cache
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from core.config import get_settings

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)

# Groq speaks the OpenAI chat-completions dialect, so this is a plain HTTP
# call via httpx (already a dependency) rather than another vendor SDK —
# one less pinned package in an environment where installs are awkward.
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_TIMEOUT_SECONDS = 20.0

_JSON_INSTRUCTION = (
    "Respond with a single JSON object and nothing else — no prose, no "
    "markdown fences. It must validate against this JSON Schema:\n"
)


def _resolve_provider() -> str | None:
    """Which provider to call: "gemini", "groq", or None if unconfigured.

    Kept as a function (not a module constant) so a settings change is picked
    up without a reimport.
    """
    settings = get_settings()
    choice = (settings.LLM_PROVIDER or "auto").strip().lower()

    if choice == "gemini":
        return "gemini" if settings.GEMINI_API_KEY else None
    if choice == "groq":
        return "groq" if settings.GROQ_API_KEY else None
    if choice != "auto":
        logger.warning(
            "Unknown LLM_PROVIDER=%r; expected 'gemini', 'groq' or 'auto'. "
            "Falling back to auto-detection.",
            choice,
        )

    # auto: prefer the incumbent, so adding a second key is never a silent
    # switch of which model is answering.
    if settings.GEMINI_API_KEY:
        return "gemini"
    if settings.GROQ_API_KEY:
        return "groq"
    return None


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------


@lru_cache
def _get_gemini_client():
    """Lazily build a cached Gemini client, or None if no API key is set.

    Cached so we don't reconstruct the client on every call; a missing key
    (e.g. in tests/CI, which never call this module directly — they
    monkeypatch `generate_structured` instead) is a normal, expected state,
    not an error. The SDK is imported inside the function rather than at
    module scope so a Groq-only deployment doesn't need `google-genai`
    installed at all.
    """
    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        return None
    from google import genai

    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _gemini_generate(prompt: str, response_schema: type[ModelT]) -> ModelT | None:
    from google.genai import types

    client = _get_gemini_client()
    if client is None:
        logger.warning("Gemini client unavailable (no GEMINI_API_KEY); returning None.")
        return None

    # NOT gemini-2.5-flash by default: it still appears in models.list() but
    # generateContent rejects it for keys created after its retirement ("no
    # longer available to new users", HTTP 404), so the whole LLM layer
    # silently fell back to its hardcoded defaults. Found only by reading the
    # actual API error - the fallbacks are so well-behaved that nothing looked
    # broken from outside. Hence the model name is configuration, not code.
    model_name = get_settings().GEMINI_MODEL

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - must never raise out of this function
        # Include the reason: "call failed" alone can't distinguish a dead key
        # from an exhausted quota (429) from a retired model (404), and this
        # layer's fallbacks are quiet enough that the log is the only signal.
        logger.warning(
            "Gemini API call failed (%s: %s); caller must use its hardcoded fallback.",
            type(exc).__name__,
            str(exc)[:200],
        )
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


# ---------------------------------------------------------------------------
# Groq (OpenAI-compatible chat completions)
# ---------------------------------------------------------------------------


def _strictify(schema: dict[str, Any]) -> dict[str, Any]:
    """Make a Pydantic-generated JSON Schema acceptable to strict structured
    output: every object must list all its properties as required and forbid
    extras. Walks nested definitions rather than only fixing the top level.
    """
    if not isinstance(schema, dict):
        return schema
    out = dict(schema)
    if out.get("type") == "object" or "properties" in out:
        props = out.get("properties") or {}
        out["properties"] = {k: _strictify(v) for k, v in props.items()}
        out["required"] = list(props)
        out["additionalProperties"] = False
    if "items" in out:
        out["items"] = _strictify(out["items"])
    for key in ("$defs", "definitions"):
        if isinstance(out.get(key), dict):
            out[key] = {k: _strictify(v) for k, v in out[key].items()}
    return out


def _groq_payload(
    prompt: str, response_schema: type[ModelT], model: str, *, strict: bool
) -> dict[str, Any]:
    """Request body for one Groq attempt.

    `strict=True` uses json_schema structured output, where the model is
    constrained server-side. `strict=False` uses the older json_object mode
    and carries the schema in the prompt instead — a fallback for models that
    reject json_schema (support varies by model on Groq; llama-3.3-70b is one
    that does not take it). Either way the reply is validated against the
    Pydantic schema before any caller sees it, so the weaker mode cannot
    smuggle an off-schema value through — it only fails more often, into the
    same hardcoded-fallback path as an outage.
    """
    schema = _strictify(response_schema.model_json_schema())
    user_content = prompt
    if strict:
        response_format: dict[str, Any] = {
            "type": "json_schema",
            "json_schema": {
                "name": response_schema.__name__,
                "schema": schema,
                "strict": True,
            },
        }
    else:
        response_format = {"type": "json_object"}
        user_content = f"{prompt}\n\n{_JSON_INSTRUCTION}{json.dumps(schema)}"

    return {
        "model": model,
        "messages": [{"role": "user", "content": user_content}],
        # Deterministic: these are tagging/phrasing calls, not creative ones.
        "temperature": 0,
        "response_format": response_format,
    }


def _groq_generate(prompt: str, response_schema: type[ModelT]) -> ModelT | None:
    settings = get_settings()
    if not settings.GROQ_API_KEY:
        logger.warning("Groq client unavailable (no GROQ_API_KEY); returning None.")
        return None

    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    model = settings.GROQ_MODEL

    # Try server-side schema enforcement first, then degrade to json_object
    # mode: a 400 for an unsupported response_format is a model/config
    # mismatch we can recover from, not an outage.
    for strict in (True, False):
        try:
            response = httpx.post(
                _GROQ_URL,
                headers=headers,
                json=_groq_payload(prompt, response_schema, model, strict=strict),
                timeout=_GROQ_TIMEOUT_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001 - must never raise out of this function
            logger.warning(
                "Groq API call failed (%s: %s); caller must use its hardcoded fallback.",
                type(exc).__name__,
                str(exc)[:200],
            )
            return None

        if response.status_code == 400 and strict:
            logger.info(
                "Groq model %r rejected json_schema structured output; retrying in "
                "json_object mode.",
                model,
            )
            continue

        if response.status_code != 200:
            logger.warning(
                "Groq API returned HTTP %s (%s); caller must use its hardcoded fallback.",
                response.status_code,
                str(getattr(response, "text", ""))[:200],
            )
            return None

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            logger.warning("Groq response had an unexpected shape; returning None.")
            return None

        try:
            return response_schema.model_validate_json(content)
        except (ValidationError, ValueError, TypeError):
            logger.warning("Groq response failed schema validation; returning None.")
            return None

    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def generate_structured(prompt: str, response_schema: type[ModelT]) -> ModelT | None:
    """Call the configured LLM with a prompt, constrained to emit JSON
    matching `response_schema`, and return a validated instance of it.

    Returns None (never raises) if: no provider/API key is configured, the
    network call fails for any reason, or the response can't be validated
    against `response_schema`. Callers must always have a hardcoded fallback
    for the None case.
    """
    provider = _resolve_provider()
    if provider == "gemini":
        return _gemini_generate(prompt, response_schema)
    if provider == "groq":
        return _groq_generate(prompt, response_schema)

    logger.warning(
        "No LLM provider configured (set GEMINI_API_KEY or GROQ_API_KEY); returning None."
    )
    return None
