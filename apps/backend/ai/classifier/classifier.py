"""ML risk classifier — the trained Phase 3/4 model, served.

Loads `ml/eval/baseline_model.joblib`: TF-IDF (word + char n-grams) +
Logistic Regression, the model that won the Phase 4 comparison. The
sentence-embedding alternative was evaluated and rejected — with features
matched the two were statistically indistinguishable, so the tie was broken
on deployment cost (see `ml/eval/comparison_report.md`).

FEATURES — and why there are only two
--------------------------------------
`task_text` and `category`. The model is trained on exactly these and nothing
else, because they are exactly what a `Job` carries at assessment time.

It does NOT use `tools_available`: the dataset records it but `Job` has no
such column and intake never asks, so training on it would be train/serve
skew (measured: fitting with tools scored macro-F1 0.613 but served blanked —
all production could do — it fell to 0.549). Everything else on a dataset row
is an *output* of assessment and would leak the label.

It no longer uses `user_skill` either, dropped 2026-08-02 with the field
itself. That feature was a leaked label: the seed data chose it to fit each
example's narrative, putting 91% of `Experienced` rows on level 4 with none
at all on levels 1-3, so the model returned 4 for an experienced user
changing a light bulb and 1 for a beginner rewiring a consumer unit. Once the
data was rebalanced (`ml/rebalance_skill.py`) it became the weakest
coefficient block in the model and the prediction was identical across all
three values — it had stopped earning its place, and it was unverifiable
self-report regardless (srs.md §3). Removing it moved grouped-CV macro-F1
0.349 -> 0.344 and high-risk recall 0.647 -> 0.633, both inside noise.
Skill-based escalation was always the rule engine's job and stays there:
`fixed_wiring_work` now carries floor 3 for everyone.

FAILURE IS LOUD, NEVER "SAFE"
-----------------------------
If the artifact is missing, unreadable, or produces an out-of-range value,
`classify()` RAISES. It must never return a low risk level to paper over a
broken model — `assess_job` catches the exception, writes `ai_logs`, and
marks the assessment `failed` with risk 5 (CLAUDE.md: "AI pipeline failures
must set assessment_status = failed and block the DIY recommendation — never
silently fall back to a 'safe' result").

This is only half the decision. `final_risk = max(ML, rules)`, and the
deterministic rule engine in `ai/rule_engine/` is what actually guarantees
safety-critical escalation — this model's high-risk recall is around 0.65
(see `ml/eval/baseline_report.md`), nowhere near `prd.md` §7's target.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

# Repo root: apps/backend/ai/classifier/classifier.py -> up 4 levels.
_DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[4] / "ml" / "eval" / "baseline_model.joblib"

MODEL_PATH = Path(os.environ.get("BUILDSAFE_MODEL_PATH", _DEFAULT_MODEL_PATH))

MIN_RISK_LEVEL = 1
MAX_RISK_LEVEL = 5


class ModelUnavailableError(RuntimeError):
    """Raised when the trained model cannot be loaded or used.

    Deliberately fatal to the assessment. Callers must fail the assessment
    rather than substitute a default risk level.
    """


@lru_cache(maxsize=1)
def _load_model():
    """Load and cache the fitted pipeline. Raises if anything is wrong."""
    if not MODEL_PATH.exists():
        raise ModelUnavailableError(
            f"trained model not found at {MODEL_PATH}. Run "
            f"`python ml/train_baseline.py` to build it, or set "
            f"BUILDSAFE_MODEL_PATH to an existing artifact."
        )
    try:
        import joblib

        bundle = joblib.load(MODEL_PATH)
        model = bundle["model"]
    except ModelUnavailableError:
        raise
    except Exception as exc:  # noqa: BLE001 - re-raised as a typed error below
        raise ModelUnavailableError(f"failed to load model from {MODEL_PATH}: {exc}") from exc

    logger.info("classifier: loaded %s (features=%s)", MODEL_PATH, bundle.get("features"))
    return model


def warmup() -> bool:
    """Load the model eagerly. Returns True if it is usable.

    Called at app startup so a broken deployment is visible immediately in
    the logs rather than only when the first user submits a job. Never
    raises: the process still boots, because auth, job intake and follow-ups
    all work without the classifier. `/health/ready` reports the degraded
    state, and assessment itself fails loudly rather than guessing.
    """
    try:
        _load_model()
        return True
    except ModelUnavailableError:
        logger.exception("classifier: model unavailable at startup")
        return False


@lru_cache(maxsize=1)
def _trained_categories() -> tuple[str, ...]:
    """The exact `category` values the model was fitted on.

    Read off the fitted OneHotEncoder rather than hardcoded, so this can
    never drift from the artifact actually being served. `user_skill` used to
    be the second column here; it was dropped as a feature on 2026-08-02 (see
    the module docstring).
    """
    model = _load_model()
    try:
        encoder = model.named_steps["features"].named_transformers_["cat"]
        return tuple(encoder.categories_[0])
    except Exception:  # noqa: BLE001 - vocabulary is advisory, never fatal
        logger.warning("classifier: could not read trained vocabulary from the model")
        return ()


def _canonicalize(value: str, vocabulary: tuple[str, ...], field: str) -> str:
    """Snap `value` onto the trained vocabulary, case/whitespace-insensitively.

    The encoder is `handle_unknown="ignore"`, so an off-vocabulary value does
    not error - it emits an all-zero block and the prediction silently falls
    back to the text features alone. That is not a small effect: measured on
    the pre-2026-08-02 model, "how do i change my light bulb" scored 1 with
    user_skill "Beginner" and 5 with "beginner", purely because the second
    matched nothing it was fitted on. `user_skill` is gone now, but
    `category` is still one-hot encoded and reaches this the same way - via
    LLM tagging, which is constrained to the fixed set but normalises to
    lowercase, so the guard stays.

    A genuinely unknown value is passed through unchanged (the encoder still
    ignores it) and logged, because guessing which trained value the caller
    meant would be worse than a loud degradation.
    """
    if not vocabulary or not value:
        return value
    if value in vocabulary:
        return value
    folded = value.strip().casefold()
    for known in vocabulary:
        if known.casefold() == folded:
            return known
    logger.warning(
        "classifier: %s=%r is not one of the trained values %s; the model will "
        "ignore it and predict from the task text alone",
        field,
        value,
        vocabulary,
    )
    return value


def classify(description: str, category: str) -> tuple[int, float]:
    """Predict (risk_level, confidence) for a job.

    `confidence` is the model's probability for the predicted class. It is
    NOT calibrated — treat it as a relative signal only, and see
    `ml/eval/baseline_report.md` before surfacing it to users.

    Raises ModelUnavailableError if the model cannot produce a usable
    prediction. Never returns a fallback risk level.
    """
    model = _load_model()
    known_categories = _trained_categories()

    try:
        import pandas as pd

        frame = pd.DataFrame(
            {
                "task_text": [description or ""],
                "category": [_canonicalize(category or "general", known_categories, "category")],
            }
        )
        risk = int(model.predict(frame)[0])
        confidence = float(max(model.predict_proba(frame)[0]))
    except Exception as exc:  # noqa: BLE001 - re-raised as a typed error
        raise ModelUnavailableError(f"model prediction failed: {exc}") from exc

    if not MIN_RISK_LEVEL <= risk <= MAX_RISK_LEVEL:
        # A model returning something outside the ordinal scale is broken,
        # not merely wrong. Fail rather than clamp - clamping would hide it.
        raise ModelUnavailableError(
            f"model returned risk level {risk} outside [{MIN_RISK_LEVEL}, {MAX_RISK_LEVEL}]"
        )

    return risk, confidence
