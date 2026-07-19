"""TEMPORARY placeholder for Phase 3/4. NOT a real ML model.

Phase 3 (TF-IDF + Logistic Regression baseline) and Phase 4 (sentence-
transformer + classifier) have not been built yet — see phases.md. This
module exists only to prove the `final_risk = max(ML, rules)` wiring works
end-to-end. It uses a trivial keyword-scoring heuristic, not a trained
model, and must be replaced before Phase 3/4's exit check (phases.md) can
pass. Do not treat this as production-safe or as representative of real
model accuracy/confidence.
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
