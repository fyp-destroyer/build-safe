"""ML risk classifier — the trained Phase 3/4 model (no longer a placeholder).

Serves `ml/eval/baseline_model.joblib`. Failure is loud: `classify()` raises
`ModelUnavailableError` rather than returning a fallback risk level, so a
broken model fails the assessment instead of silently reporting "safe".
See classifier.py's module docstring.
"""

from ai.classifier.classifier import ModelUnavailableError, classify, warmup

__all__ = ["classify", "warmup", "ModelUnavailableError"]
