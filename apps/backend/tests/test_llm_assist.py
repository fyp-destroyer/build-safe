"""ai/rule_engine/llm_assist.py — category tagging + follow-up phrasing.

Mocks `ai.rule_engine.llm_assist.generate_structured` throughout so the
test suite never makes a real network call to Gemini (no API key required
to run pytest, matching CI). The single most important test here is
`test_tag_category_falls_back_to_general_on_hallucinated_category` — it
mirrors the rule-engine-never-de-escalates test's importance: an
LLM-invented category string must never reach the database.
"""

from unittest.mock import patch

from ai.rule_engine.llm_assist import (
    _DEFAULT_FOLLOWUP_QUESTIONS,
    CategoryTag,
    PhrasedQuestion,
    phrase_followup_question,
    tag_category,
)
from schemas.job import TASK_CATEGORIES


def test_tag_category_falls_back_to_general_when_llm_unavailable():
    """generate_structured returning None (LLM down / no API key / network
    error) must still yield a category from the fixed set."""
    with patch("ai.rule_engine.llm_assist.generate_structured", return_value=None):
        category = tag_category("rewire the main electrical panel")

    assert category in TASK_CATEGORIES
    assert category == "general"


def test_tag_category_falls_back_to_general_on_hallucinated_category():
    """THE most important test in this file: if Gemini returns a category
    string outside the fixed 9-value set (a hallucination), tag_category
    must never crash and must never let that string reach the caller —
    it must fall back to "general" (rules.md §4 / defense in depth)."""
    hallucinated = CategoryTag(category="demolition_and_asbestos_removal")
    with patch("ai.rule_engine.llm_assist.generate_structured", return_value=hallucinated):
        category = tag_category("knock down some walls")

    assert category == "general"
    assert category in TASK_CATEGORIES


def test_tag_category_accepts_case_insensitive_valid_category():
    """A valid category returned with different casing should still be
    trusted (normalized to lowercase), not rejected as invalid."""
    valid = CategoryTag(category="Electrical")
    with patch("ai.rule_engine.llm_assist.generate_structured", return_value=valid):
        category = tag_category("replace a light switch")

    assert category == "electrical"


def test_phrase_followup_question_falls_back_when_llm_unavailable():
    """generate_structured returning None must yield a non-empty hardcoded
    fallback string, never block/error the job flow."""
    with patch("ai.rule_engine.llm_assist.generate_structured", return_value=None):
        question = phrase_followup_question("power_isolated", "electrical")

    assert question.strip()
    assert question == _DEFAULT_FOLLOWUP_QUESTIONS["power_isolated"]


def test_phrase_followup_question_falls_back_on_empty_llm_answer():
    """An empty/whitespace question from Gemini is treated the same as
    unavailable — never surface a blank question to the user."""
    blank = PhrasedQuestion(question="   ")
    with patch("ai.rule_engine.llm_assist.generate_structured", return_value=blank):
        question = phrase_followup_question("gas_line_present", "plumbing")

    assert question.strip()
    assert question == _DEFAULT_FOLLOWUP_QUESTIONS["gas_line_present"]


def test_phrase_followup_question_uses_llm_wording_when_available():
    """When Gemini is available and returns a valid question, its wording
    is used (still just phrasing — the field itself is a fixed input)."""
    phrased = PhrasedQuestion(question="Is the breaker for this circuit switched off?")
    with patch("ai.rule_engine.llm_assist.generate_structured", return_value=phrased):
        question = phrase_followup_question("power_isolated", "electrical")

    assert question == "Is the breaker for this circuit switched off?"
