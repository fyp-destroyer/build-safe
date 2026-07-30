"""ML risk classifier — the trained Phase 3/4 model, served.

Loads `ml/eval/baseline_model.joblib`: TF-IDF (word + char n-grams) +
Logistic Regression, the model that won the Phase 4 comparison. The
sentence-embedding alternative was evaluated and rejected — with features
matched the two were statistically indistinguishable, so the tie was broken
on deployment cost (see `ml/eval/comparison_report.md`).

FEATURES — and why there are only three
---------------------------------------
`task_text`, `category`, `user_skill`. The model is trained on exactly these
and nothing else, because they are exactly what a `Job` carries at assessment
time. In particular it does NOT use `tools_available`: the dataset records it
but `Job` has no such column and intake never asks, so training on it would
be train/serve skew (measured: fitting with tools scored macro-F1 0.613 but
served blanked — all production could do — it fell to 0.549). Everything else
on a dataset row is an *output* of assessment and would leak the label.

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


def classify(description: str, category: str, user_skill: str = "") -> tuple[int, float]:
    """Predict (risk_level, confidence) for a job.

    `confidence` is the model's probability for the predicted class. It is
    NOT calibrated — treat it as a relative signal only, and see
    `ml/eval/baseline_report.md` before surfacing it to users.

    Raises ModelUnavailableError if the model cannot produce a usable
    prediction. Never returns a fallback risk level.
    """
    model = _load_model()

    try:
        import pandas as pd

        frame = pd.DataFrame(
            {
                "task_text": [description or ""],
                "category": [category or "general"],
                "user_skill": [user_skill or "Beginner"],
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
