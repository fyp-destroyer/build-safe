"""The served ML classifier: real predictions, and loud failure.

The property that matters most here is NOT accuracy - that is measured in
ml/eval/baseline_report.md. It is that a broken model can never quietly
produce a low risk level. CLAUDE.md: "AI pipeline failures must set
assessment_status = failed and block the DIY recommendation - never silently
fall back to a 'safe' result."

Pure-logic: no database, no network.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from ai.classifier import classify, warmup
from ai.classifier.classifier import (
    MAX_RISK_LEVEL,
    MIN_RISK_LEVEL,
    ModelUnavailableError,
    _load_model,
)


@pytest.fixture(autouse=True)
def _clear_model_cache():
    """The loader is lru_cached; clear it so patched failures actually bite."""
    _load_model.cache_clear()
    yield
    _load_model.cache_clear()


def test_model_artifact_loads():
    assert warmup() is True


def test_skill_and_category_casing_does_not_change_the_prediction():
    """Regression (2026-08-01): the one-hot encoder is
    `handle_unknown="ignore"`, so an off-vocabulary value emitted an all-zero
    block and the prediction silently fell back to the task text alone.

    Measured on the shipped artifact, "how do i change my light bulb" scored
    1 with user_skill "Beginner" and 5 with "beginner" — the same job, a
    four-level swing, with nothing logged. `skill_level` is a free `str` at
    the API boundary, so only a UI convention was keeping the two aligned.
    """
    desc = "how do i change my light bulb"
    canonical = classify(desc, "electrical", "Beginner")
    assert classify(desc, "electrical", "beginner") == canonical
    assert classify(desc, "electrical", "  BEGINNER  ") == canonical
    assert classify(desc, "ELECTRICAL", "Beginner") == canonical

    multiword = classify(desc, "electrical", "Some experience")
    assert classify(desc, "electrical", "some experience") == multiword


def test_unknown_skill_is_passed_through_not_guessed():
    """A value that matches nothing trained is left alone (the encoder
    ignores it) rather than being mapped to a guess — a wrong guess would be
    a silent, invented input to a safety decision."""
    risk, confidence = classify("replace a socket", "electrical", "Wizard")
    assert MIN_RISK_LEVEL <= risk <= MAX_RISK_LEVEL
    assert 0.0 <= confidence <= 1.0


def test_predictions_are_in_range_and_carry_a_confidence():
    for desc, cat, skill in [
        ("paint a bedroom wall with a roller", "painting", "Beginner"),
        ("I can smell gas near the boiler", "plumbing", "Beginner"),
        ("rewire the consumer unit in my garage", "electrical", "Experienced"),
        ("assemble a flat pack wardrobe", "general", "Some experience"),
    ]:
        risk, confidence = classify(desc, cat, skill)
        assert MIN_RISK_LEVEL <= risk <= MAX_RISK_LEVEL
        assert 0.0 <= confidence <= 1.0


def test_obviously_dangerous_beats_obviously_safe():
    """A weak sanity check, deliberately not an accuracy assertion.

    The model's real accuracy is measured in ml/eval/, not here - pinning
    exact predictions in a unit test would make it fail every retrain. This
    only asserts the ordering has not inverted completely.
    """
    danger, _ = classify("I can smell gas near the boiler", "plumbing", "Beginner")
    safe, _ = classify("paint a bedroom wall with a roller", "painting", "Beginner")
    assert danger > safe


# --------------------------------------------------------------- fail loudly
def test_missing_artifact_raises_rather_than_returning_a_safe_default():
    with patch("ai.classifier.classifier.MODEL_PATH", Path("/nonexistent/model.joblib")):
        with pytest.raises(ModelUnavailableError):
            classify("anything", "general", "Beginner")


def test_unreadable_artifact_raises():
    with patch("joblib.load", side_effect=ValueError("corrupt pickle")):
        with pytest.raises(ModelUnavailableError):
            classify("anything", "general", "Beginner")


def test_out_of_range_prediction_raises_instead_of_being_clamped():
    """Clamping would hide a broken model; failing surfaces it."""

    class Rogue:
        def predict(self, _):
            return [99]

        def predict_proba(self, _):
            return [[1.0]]

    with patch("ai.classifier.classifier._load_model", return_value=Rogue()):
        with pytest.raises(ModelUnavailableError, match="outside"):
            classify("anything", "general", "Beginner")


def test_prediction_error_raises():
    class Exploding:
        def predict(self, _):
            raise RuntimeError("boom")

        def predict_proba(self, _):
            raise RuntimeError("boom")

    with patch("ai.classifier.classifier._load_model", return_value=Exploding()):
        with pytest.raises(ModelUnavailableError):
            classify("anything", "general", "Beginner")


def test_warmup_reports_false_instead_of_raising():
    """Startup must not crash the app; it reports and lets /health/ready tell."""
    with patch("ai.classifier.classifier.MODEL_PATH", Path("/nonexistent/model.joblib")):
        assert warmup() is False


def test_empty_input_still_produces_a_valid_prediction():
    """Defensive: empty text must not blow up the vectoriser."""
    risk, confidence = classify("", "", "")
    assert MIN_RISK_LEVEL <= risk <= MAX_RISK_LEVEL
    assert 0.0 <= confidence <= 1.0
