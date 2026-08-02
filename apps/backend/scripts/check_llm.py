"""Confirm the configured LLM provider actually answers.

The LLM layer is deliberately silent when it fails — every call falls back to
a hardcoded default, so a dead API key, a retired model or a typo'd provider
name looks exactly like a working system with slightly blander wording. That
already cost a debugging session once (a retired `gemini-2.5-flash` meant the
whole layer was falling back and nothing looked broken). This script is the
loud version: it makes one real call of each kind and prints what came back.

    python scripts/check_llm.py           # exercise the configured provider
    python scripts/check_llm.py --list    # list models this key can use

Exit code is 0 only if every call returned a validated result.
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from ai.llm.client import _resolve_provider  # noqa: E402
from ai.rule_engine.llm_assist import (  # noqa: E402
    phrase_followup_question,
    tag_category,
    tag_hazards_result,
)
from core.config import get_settings  # noqa: E402


def _list_models() -> int:
    """Print the model ids the configured key is allowed to call.

    Answers the question the docs can't: model lineups change, and the only
    authority on what *your* key can use is the provider's own endpoint.
    """
    settings = get_settings()
    provider = _resolve_provider()

    if provider == "groq":
        resp = httpx.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
            timeout=20.0,
        )
        if resp.status_code != 200:
            print(f"Groq /models returned HTTP {resp.status_code}: {resp.text[:300]}")
            return 1
        for model in sorted(m["id"] for m in resp.json().get("data", [])):
            marker = "  <-- configured" if model == settings.GROQ_MODEL else ""
            print(f"  {model}{marker}")
        return 0

    if provider == "gemini":
        from google import genai

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        for model in client.models.list():
            name = model.name.removeprefix("models/")
            marker = "  <-- configured" if name == settings.GEMINI_MODEL else ""
            print(f"  {name}{marker}")
        return 0

    print("No provider configured — set GEMINI_API_KEY or GROQ_API_KEY in .env")
    return 1


def _check_calls() -> int:
    settings = get_settings()
    provider = _resolve_provider()
    model = settings.GROQ_MODEL if provider == "groq" else settings.GEMINI_MODEL

    print(f"LLM_PROVIDER={settings.LLM_PROVIDER!r} -> resolved provider: {provider!r}")
    if provider is None:
        print("FAIL: no API key configured; the whole LLM layer is running on fallbacks.")
        return 1
    print(f"model: {model}\n")

    failures = 0

    # Each call is a real one. A None/fallback result is the failure signal —
    # that's exactly the silent degradation this script exists to surface.
    category = tag_category("i want to replace my ceiling fans")
    ok = category != "general"
    print(f"{'ok  ' if ok else 'FAIL'} tag_category            -> {category!r}")
    failures += 0 if ok else 1
    if not ok:
        print("       ('general' is the hardcoded fallback — the call likely failed)")

    tagged = tag_hazards_result("i want to replace my ceiling fans", "electrical")
    ok = tagged is not None
    summary = "None" if tagged is None else f"tags={tagged.rule_ids!r} ask={tagged.ask_fields!r}"
    print(f"{'ok  ' if ok else 'FAIL'} tag_hazards             -> {summary}")
    failures += 0 if ok else 1
    if not ok:
        print("       (None means the call failed; empty lists mean 'ran, found nothing')")

    # Evidence grounding: a bulb swap must NOT come back tagged as fixed
    # wiring or work at height. Both were observed live on 2026-07-31/08-01
    # and are what the evidence requirement exists to stop, so a regression
    # here is worth surfacing from the same one-command check.
    bulb = tag_hazards_result("how do i change my light bulb", "electrical")
    if bulb is None:
        print("skip  bulb over-tagging    -> LLM unavailable")
    else:
        overtagged = [r for r in bulb.rule_ids if r in ("fixed_wiring_work", "work_at_height")]
        ok = not overtagged
        print(
            f"{'ok  ' if ok else 'FAIL'} bulb over-tagging       -> "
            f"tags={bulb.rule_ids!r} ask={bulb.ask_fields!r}"
        )
        failures += 0 if ok else 1
        if not ok:
            print(f"       (a light bulb is a consumable, not fixed wiring: {overtagged})")

    question = phrase_followup_question("power_isolated", "electrical")
    print(f"ok   phrase_followup_question -> {question!r}")
    print("       (this one always returns text; a hardcoded default if the call failed)")

    print()
    if failures:
        # Deliberately ASCII: this runs in the Windows console, which is not
        # reliably UTF-8, and a mojibake'd diagnostic is a worse diagnostic.
        print(f"{failures} call(s) fell back to hardcoded defaults - check key/model above.")
        print("Re-run with --verbose to see the actual cause (HTTP status, validation error).")
        print("A 429 means quota exhausted, not a broken key.")
    else:
        print("All calls returned live results.")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list available models and exit")
    parser.add_argument("--verbose", action="store_true", help="show client warning logs")
    args = parser.parse_args()

    # The client logs failures as warnings; surface them on request so a
    # failure shows its actual cause (HTTP status, validation error) rather
    # than just a fallback value.
    logging.basicConfig(level=logging.INFO if args.verbose else logging.ERROR)

    return _list_models() if args.list else _check_calls()


if __name__ == "__main__":
    raise SystemExit(main())
