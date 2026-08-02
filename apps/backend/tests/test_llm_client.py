"""ai/llm/client.py — provider selection and the Groq transport.

No real network call is made: `httpx.post` is mocked. What matters here is
not that Groq works (that's Groq's problem) but that every way it can
misbehave still lands on `None`, which every caller treats as "LLM
unavailable" and answers with a hardcoded safe default (rules.md §4).

The single most important test is
`test_groq_off_schema_response_returns_none` — a provider that returns
plausible-looking JSON of the wrong shape must never reach a caller.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

import ai.llm.client as llm_client
from ai.llm.client import _resolve_provider, _strictify, generate_structured


@pytest.fixture(autouse=True)
def _reset_model_capability_cache():
    """The client remembers, for the life of the process, which models reject
    json_schema — so it can stop wasting a 400 on every call. That memory
    would otherwise leak between tests: whichever test ran first would decide
    how many HTTP calls every later test makes."""
    llm_client._GROQ_NO_JSON_SCHEMA.clear()
    yield
    llm_client._GROQ_NO_JSON_SCHEMA.clear()


class _Schema(BaseModel):
    category: str


def _settings(**overrides):
    """A stand-in for the cached Settings object with only the LLM fields."""
    defaults = {
        "LLM_PROVIDER": "auto",
        "GEMINI_API_KEY": "",
        "GROQ_API_KEY": "",
        "GEMINI_MODEL": "gemini-3.1-flash-lite",
        "GROQ_MODEL": "llama-3.3-70b-versatile",
    }
    return MagicMock(**{**defaults, **overrides})


def _patch_settings(**overrides):
    return patch("ai.llm.client.get_settings", return_value=_settings(**overrides))


def _response(status_code: int, content: str = "", json_body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = (
        json_body if json_body is not None else {"choices": [{"message": {"content": content}}]}
    )
    return resp


# --- provider selection ----------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"GEMINI_API_KEY": "g"}, "gemini"),
        ({"GROQ_API_KEY": "q"}, "groq"),
        # Both keys present and no explicit choice: keep the incumbent, so
        # adding a Groq key can never silently change which model answers.
        ({"GEMINI_API_KEY": "g", "GROQ_API_KEY": "q"}, "gemini"),
        ({"LLM_PROVIDER": "groq", "GEMINI_API_KEY": "g", "GROQ_API_KEY": "q"}, "groq"),
        ({"LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "g", "GROQ_API_KEY": "q"}, "gemini"),
        # Explicitly named provider whose key is missing must NOT silently
        # fall through to the other one — that would hide a config error.
        ({"LLM_PROVIDER": "groq", "GEMINI_API_KEY": "g"}, None),
        ({}, None),
        # A typo'd provider name degrades to auto-detection, with a warning.
        ({"LLM_PROVIDER": "gemeni", "GROQ_API_KEY": "q"}, "groq"),
        ({"LLM_PROVIDER": "GROQ", "GROQ_API_KEY": "q"}, "groq"),
    ],
)
def test_resolve_provider(overrides, expected):
    with _patch_settings(**overrides):
        assert _resolve_provider() == expected


def test_no_provider_configured_returns_none_without_raising():
    """The whole layer must degrade to hardcoded fallbacks, never error."""
    with _patch_settings():
        assert generate_structured("anything", _Schema) is None


# --- Groq transport --------------------------------------------------------


def test_groq_structured_success():
    with (
        _patch_settings(GROQ_API_KEY="q"),
        patch(
            "ai.llm.client.httpx.post", return_value=_response(200, '{"category": "electrical"}')
        ) as post,
    ):
        result = generate_structured("tag this", _Schema)

    assert isinstance(result, _Schema)
    assert result.category == "electrical"
    # First attempt asks for server-side schema enforcement.
    assert post.call_count == 1
    assert post.call_args.kwargs["json"]["response_format"]["type"] == "json_schema"


def test_groq_falls_back_to_json_object_mode_when_schema_mode_rejected():
    """Groq's json_schema support varies by model (llama-3.3-70b rejects it
    with a 400). That's a recoverable config mismatch, not an outage: retry
    in json_object mode with the schema carried in the prompt."""
    responses = [_response(400), _response(200, '{"category": "plumbing"}')]
    with (
        _patch_settings(GROQ_API_KEY="q"),
        patch("ai.llm.client.httpx.post", side_effect=responses) as post,
    ):
        result = generate_structured("tag this", _Schema)

    assert result is not None and result.category == "plumbing"
    assert post.call_count == 2
    second = post.call_args_list[1].kwargs["json"]
    assert second["response_format"] == {"type": "json_object"}
    # The schema has to travel in the prompt instead, or the model has no
    # idea what shape to emit.
    assert "category" in second["messages"][0]["content"]


def test_groq_off_schema_response_returns_none():
    """THE important one: a 200 carrying valid JSON of the WRONG shape must
    never reach a caller. Validation is what makes a second provider safe to
    add at all — an unconstrained reply degrades to the same `None` as an
    outage, and callers answer from hardcoded defaults."""
    with (
        _patch_settings(GROQ_API_KEY="q"),
        patch(
            "ai.llm.client.httpx.post",
            return_value=_response(200, '{"risk_level": 1, "verdict": "totally safe"}'),
        ),
    ):
        assert generate_structured("tag this", _Schema) is None


def test_groq_prose_instead_of_json_returns_none():
    with (
        _patch_settings(GROQ_API_KEY="q"),
        patch(
            "ai.llm.client.httpx.post",
            return_value=_response(200, "Sure! Here's the category: electrical"),
        ),
    ):
        assert generate_structured("tag this", _Schema) is None


@pytest.mark.parametrize(
    "content",
    [
        '```json\n{"category": "roofing"}\n```',
        '```\n{"category": "roofing"}\n```',
        'Here you go:\n{"category": "roofing"}',
        '  {"category": "roofing"}  ',
    ],
)
def test_groq_json_wrapped_in_fences_or_prose_is_still_accepted(content):
    """json_object mode is the fallback for models WITHOUT server-side schema
    enforcement — the ones most likely to wrap the object in markdown fences.
    A right-shaped answer shouldn't be thrown away over packaging."""
    with (
        _patch_settings(GROQ_API_KEY="q"),
        patch("ai.llm.client.httpx.post", side_effect=[_response(400), _response(200, content)]),
    ):
        result = generate_structured("tag this", _Schema)

    assert result is not None and result.category == "roofing"


def test_unwrapping_does_not_weaken_schema_validation():
    """Unwrapping normalises TEXT only. A fenced object of the wrong shape
    must still be rejected — otherwise the leniency would be a hole."""
    with (
        _patch_settings(GROQ_API_KEY="q"),
        patch(
            "ai.llm.client.httpx.post",
            return_value=_response(200, '```json\n{"risk_level": 1}\n```'),
        ),
    ):
        assert generate_structured("tag this", _Schema) is None


@pytest.mark.parametrize("status", [401, 429, 500])
def test_groq_http_error_returns_none(status):
    """Bad key, rate limit, provider outage — all the same to the caller."""
    with (
        _patch_settings(GROQ_API_KEY="q"),
        patch("ai.llm.client.httpx.post", return_value=_response(status)),
    ):
        assert generate_structured("tag this", _Schema) is None


def test_groq_400_on_both_attempts_returns_none():
    """A 400 that isn't about response_format (e.g. a retired model id) must
    terminate, not loop."""
    with (
        _patch_settings(GROQ_API_KEY="q"),
        patch("ai.llm.client.httpx.post", side_effect=[_response(400), _response(400)]) as post,
    ):
        assert generate_structured("tag this", _Schema) is None
    assert post.call_count == 2


def test_groq_network_exception_never_escapes():
    with (
        _patch_settings(GROQ_API_KEY="q"),
        patch("ai.llm.client.httpx.post", side_effect=OSError("connection reset")),
    ):
        assert generate_structured("tag this", _Schema) is None


def test_groq_unexpected_response_shape_returns_none():
    with (
        _patch_settings(GROQ_API_KEY="q"),
        patch(
            "ai.llm.client.httpx.post", return_value=_response(200, json_body={"unexpected": True})
        ),
    ):
        assert generate_structured("tag this", _Schema) is None


# --- schema preparation ----------------------------------------------------


def test_strictify_marks_all_properties_required_and_forbids_extras():
    strict = _strictify(_Schema.model_json_schema())
    assert strict["required"] == ["category"]
    assert strict["additionalProperties"] is False


def test_strictify_recurses_into_nested_definitions():
    class Inner(BaseModel):
        field: str

    class Outer(BaseModel):
        inner: Inner

    strict = _strictify(Outer.model_json_schema())
    inner = strict["$defs"]["Inner"]
    assert inner["required"] == ["field"]
    assert inner["additionalProperties"] is False
