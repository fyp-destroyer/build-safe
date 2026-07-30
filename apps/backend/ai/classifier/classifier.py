"""TEMPORARY placeholder. NOT a real ML model — still a keyword heuristic.

Status as of Phase 5: Phase 3 and Phase 4 ARE complete, but their output is
not wired in here yet. The trained model that won the Phase 4 comparison is
`ml/eval/baseline_model.joblib` (TF-IDF + Logistic Regression; the
sentence-embedding alternative was evaluated and rejected — see
`ml/eval/comparison_report.md`). Loading it here is a deliberate follow-up
step, kept separate because it adds scikit-learn and a model artifact to the
serving path and deserves its own review.

Until then this module exists only to prove the `final_risk = max(ML, rules)`
wiring works end-to-end. Do not treat its output as representative of real
model accuracy or confidence.

Note the safety consequence of that gap: right now the ML half of
`max(ML, rules)` is a heuristic, so the deterministic rule engine in
`ai/rule_engine/` is what actually carries the safety guarantee.
"""

_HIGH_RISK_KEYWORDS = (
    "gas",
    "live wire",
    "live wiring",
    "electrical panel",
    "main panel",
    "load-bearing",
    "load bearing",
    "roof",
    "demolition",
)

_MEDIUM_RISK_KEYWORDS = (
    "electrical",
    "wiring",
    "plumbing",
    "gas line",
    "circuit",
    "outlet",
    "breaker",
)

_LOW_RISK_CATEGORIES = ("painting", "general")


def classify(description: str, category: str) -> tuple[int, float]:
    """Return (predicted_risk_level, confidence) from a keyword heuristic.

    THIS IS NOT A TRAINED ML MODEL. It is a placeholder so the service layer
    and API contracts can be built and tested before the real classifier
    (Phase 3/4) exists. Confidence is a fixed, low-ish value to signal that
    this prediction should not be trusted as a real model's output.

    Never returns a risk level outside 1-5.
    """
    text = f"{description} {category}".lower()

    if any(keyword in text for keyword in _HIGH_RISK_KEYWORDS):
        return 4, 0.55

    if any(keyword in text for keyword in _MEDIUM_RISK_KEYWORDS):
        return 3, 0.5

    if category.lower() in _LOW_RISK_CATEGORIES:
        return 1, 0.5

    # Default: no strong signal either way. Placeholder heuristic deliberately
    # does NOT assume "safe" with high confidence — mid-low risk, low
    # confidence, consistent with "never silently default to safe."
    return 2, 0.4
