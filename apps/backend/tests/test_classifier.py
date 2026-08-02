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


def test_category_casing_does_not_change_the_prediction():
    """Regression (2026-08-01): the one-hot encoder is
    `handle_unknown="ignore"`, so an off-vocabulary value emits an all-zero
    block and the prediction silently falls back to the task text alone.

    Measured on the artifact of the day, "how do i change my light bulb"
    scored 1 with user_skill "Beginner" and 5 with "beginner" — the same job,
    a four-level swing, nothing logged. `user_skill` is gone as a feature
    (2026-08-02) but `category` reaches the encoder the same way, so the
    guard is still load-bearing.
    """
    desc = "how do i change my light bulb"
    canonical = classify(desc, "electrical")
    assert classify(desc, "ELECTRICAL") == canonical
    assert classify(desc, "  Electrical  ") == canonical


def test_unknown_category_is_passed_through_not_guessed():
    """A value that matches nothing trained is left alone (the encoder
    ignores it) rather than being mapped to a guess — a wrong guess would be
    a silent, invented input to a safety decision."""
    risk, confidence = classify("replace a socket", "not_a_real_category")
    assert MIN_RISK_LEVEL <= risk <= MAX_RISK_LEVEL
    assert 0.0 <= confidence <= 1.0


def test_prediction_does_not_depend_on_a_removed_feature():
    """`user_skill` was dropped on 2026-08-02 because it had become a proxy
    for the label: 91% of `Experienced` rows were level 4, so the model
    returned 4 for an experienced user changing a light bulb and 1 for a
    beginner rewiring a consumer unit.

    `classify()` no longer accepts it at all, which is the strongest form of
    that guarantee — but this pins the behaviour the removal was for, so a
    future re-add has to clear the same bar.
    """
    assert classify("how do i change my light bulb", "electrical")[0] == 1
    assert classify("rewire the consumer unit in my garage", "electrical")[0] >= 4


def test_predictions_are_in_range_and_carry_a_confidence():
    for desc, cat in [
        ("paint a bedroom wall with a roller", "painting"),
        ("I can smell gas near the boiler", "plumbing"),
        ("rewire the consumer unit in my garage", "electrical"),
        ("assemble a flat pack wardrobe", "general"),
    ]:
        risk, confidence = classify(desc, cat)
        assert MIN_RISK_LEVEL <= risk <= MAX_RISK_LEVEL
        assert 0.0 <= confidence <= 1.0


def test_obviously_dangerous_beats_obviously_safe():
    """A weak sanity check, deliberately not an accuracy assertion.

    The model's real accuracy is measured in ml/eval/, not here - pinning
    exact predictions in a unit test would make it fail every retrain. This
    only asserts the ordering has not inverted completely.
    """
    danger, _ = classify("I can smell gas near the boiler", "plumbing")
    safe, _ = classify("paint a bedroom wall with a roller", "painting")
    assert danger > safe


# --------------------------------------------------------------- fail loudly
def test_missing_artifact_raises_rather_than_returning_a_safe_default():
    with patch("ai.classifier.classifier.MODEL_PATH", Path("/nonexistent/model.joblib")):
        with pytest.raises(ModelUnavailableError):
            classify("anything", "general")


def test_unreadable_artifact_raises():
    with patch("joblib.load", side_effect=ValueError("corrupt pickle")):
        with pytest.raises(ModelUnavailableError):
            classify("anything", "general")


def test_out_of_range_prediction_raises_instead_of_being_clamped():
    """Clamping would hide a broken model; failing surfaces it."""

    class Rogue:
        def predict(self, _):
            return [99]

        def predict_proba(self, _):
            return [[1.0]]

    with patch("ai.classifier.classifier._load_model", return_value=Rogue()):
        with pytest.raises(ModelUnavailableError, match="outside"):
            classify("anything", "general")


def test_prediction_error_raises():
    class Exploding:
        def predict(self, _):
            raise RuntimeError("boom")

        def predict_proba(self, _):
            raise RuntimeError("boom")

    with patch("ai.classifier.classifier._load_model", return_value=Exploding()):
        with pytest.raises(ModelUnavailableError):
            classify("anything", "general")


def test_warmup_reports_false_instead_of_raising():
    """Startup must not crash the app; it reports and lets /health/ready tell."""
    with patch("ai.classifier.classifier.MODEL_PATH", Path("/nonexistent/model.joblib")):
        assert warmup() is False


def test_empty_input_still_produces_a_valid_prediction():
    """Defensive: empty text must not blow up the vectoriser."""
    risk, confidence = classify("", "")
    assert MIN_RISK_LEVEL <= risk <= MAX_RISK_LEVEL
    assert 0.0 <= confidence <= 1.0
