"""Shared evaluation harness for the Phase 3 baseline and Phase 4 model.

Both trainers import from here so their numbers are computed by identical
code. That matters: Phase 4's exit check is a decision about *which model
ships*, and if each script computed its own metrics, a subtle difference in
how (say) high-risk recall was defined would quietly decide it.

Everything here is model-agnostic - functions take y_true/y_pred arrays, not
estimators - so a scikit-learn pipeline and a torch embedding model are
scored the same way.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score)

DATA = Path(__file__).parent / "data"
EVAL = Path(__file__).parent / "eval"

RISK_NAMES = {1: "safe_diy", 2: "diy_with_supervision", 3: "professional_recommended",
              4: "professional_required", 5: "dangerous"}
LABELS = [1, 2, 3, 4, 5]

# Levels the product treats as "do not attempt unassisted".
HIGH_RISK = (4, 5)

SAFETY_CRITICAL = ("power_isolated", "load_bearing_confirmed", "gas_line_present")

# Fields that are OUTPUTS of an assessment, not inputs a user supplies.
# Training on any of these leaks the label - measured on the 555-row dataset:
#   professional_category is None <=> risk <= 2   in 555/555 rows
#   suggested_ppe == []                           in every risk-5 row
#   unanswered safety followup    => risk 5       in all 59 rows
#   37 of 66 distinct hazard sets map to exactly one risk level
LEAKING_FIELDS = ("professional_category", "suggested_ppe", "hazards",
                  "risk_label", "followup_questions")

# What the backend genuinely knows at assessment time (architecture.md 4).
INPUT_FIELDS = ("task_text", "category", "user_skill", "tools_available")


def load(name: str) -> list[dict]:
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def labels_of(rows: list[dict]) -> np.ndarray:
    return np.array([r["risk_level"] for r in rows])


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval - stays honest at small n, unlike the normal
    approximation, which can produce bounds outside [0, 1] here."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def rule_floor(rows: list[dict]) -> np.ndarray:
    """Partial simulation of the rule engine's contribution.

    Only the "unanswered safety-critical follow-up => 5" rule is modelled,
    since that is the one encoded in the dataset. The real engine
    (ai/rule_engine/) also carries keyword hazard rules, so this UNDERSTATES
    what the deployed system escalates.
    """
    return np.array([
        5 if any(f["answer"] is None and f["field"] in SAFETY_CRITICAL
                 for f in r["followup_questions"]) else 1
        for r in rows
    ])


def safety_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Metrics framed around the failure mode that actually matters.

    Per-class recall alone misleads here: predicting 5 when the truth is 4 is
    not a safety failure (the user is still told to get a professional), but
    predicting 2 when the truth is 5 is. So this reports severity-collapsed
    recall over levels 4-5 plus the under-prediction rate, which is the
    direct measure of the false-negative risk prd.md 7 targets.
    """
    hi = np.isin(y_true, HIGH_RISK)
    hi_caught = int((np.isin(y_pred, HIGH_RISK) & hi).sum())
    hi_total = int(hi.sum())
    under = int((y_pred < y_true).sum())
    under_hi = int(((y_pred < y_true) & hi).sum())
    lo, up = wilson(hi_caught, hi_total)
    return {
        "high_risk_total": hi_total,
        "high_risk_detected_as_high_risk": hi_caught,
        "high_risk_recall_collapsed": hi_caught / hi_total if hi_total else None,
        "high_risk_recall_ci95": [round(lo, 3), round(up, 3)],
        "under_prediction_rate": under / len(y_true),
        "under_prediction_rate_high_risk": under_hi / hi_total if hi_total else None,
        "severe_under_predictions_2plus_levels": int((y_true - y_pred >= 2).sum()),
    }


def evaluate_predictions(split: str, rows: list[dict], y_pred: np.ndarray) -> dict:
    """Score predictions for one split. Model-agnostic on purpose."""
    y = labels_of(rows)
    y_pred = np.asarray(y_pred)
    # What the system actually outputs: final_risk = max(ML, rules)
    # (architecture.md 2, srs.md 8.1). The classifier is deliberately blind
    # to follow-up state so the rule engine can own that escalation, which
    # means ML-only recall understates the deployed system.
    combined = np.maximum(y_pred, rule_floor(rows))
    return {
        "split": split,
        "n": len(rows),
        "accuracy": accuracy_score(y, y_pred),
        "macro_f1": f1_score(y, y_pred, average="macro", labels=LABELS, zero_division=0),
        "per_class": classification_report(
            y, y_pred, labels=LABELS,
            target_names=[RISK_NAMES[i] for i in LABELS],
            output_dict=True, zero_division=0),
        "confusion": confusion_matrix(y, y_pred, labels=LABELS).tolist(),
        "safety": safety_metrics(y, y_pred),
        "safety_combined_with_rules": safety_metrics(y, combined),
        "rows_rescued_by_rules": int(
            (~np.isin(y_pred, HIGH_RISK) & np.isin(combined, HIGH_RISK)
             & np.isin(y, HIGH_RISK)).sum()),
    }


# --------------------------------------------------------------------- render
def per_class_table(ev: dict) -> str:
    out = ["| risk level | precision | recall | F1 | support |", "|---|---|---|---|---|"]
    for i in LABELS:
        r = ev["per_class"][RISK_NAMES[i]]
        out.append(f"| {i} — {RISK_NAMES[i]} | {r['precision']:.2f} | {r['recall']:.2f} "
                   f"| {r['f1-score']:.2f} | {int(r['support'])} |")
    return "\n".join(out)


def confusion_table(ev: dict) -> str:
    out = ["| true \\ pred | 1 | 2 | 3 | 4 | 5 |", "|---|---|---|---|---|---|"]
    for i, row in enumerate(ev["confusion"], 1):
        out.append(f"| **{i}** | " + " | ".join(str(v) for v in row) + " |")
    return "\n".join(out)


def plot_confusion(cm: list[list[int]], path: Path, title: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    arr = np.array(cm)
    fig, ax = plt.subplots(figsize=(5.5, 4.8))
    ax.imshow(arr, cmap="Blues")
    ticks = [f"{i}\n{RISK_NAMES[i][:14]}" for i in LABELS]
    ax.set_xticks(range(5), ticks, fontsize=7)
    ax.set_yticks(range(5), ticks, fontsize=7)
    ax.set_xlabel("predicted")
    ax.set_ylabel("true")
    ax.set_title(title)
    thresh = arr.max() / 2 if arr.max() else 0
    for i in range(5):
        for j in range(5):
            ax.text(j, i, arr[i, j], ha="center", va="center", fontsize=9,
                    color="white" if arr[i, j] > thresh else "black")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def print_summary(ev: dict) -> None:
    s, c = ev["safety"], ev["safety_combined_with_rules"]
    print(f"\n{ev['split']}  n={ev['n']}")
    print(f"  accuracy {ev['accuracy']:.3f}   macro-F1 {ev['macro_f1']:.3f}")
    print(f"  high-risk recall (>=4 caught as >=4): "
          f"{s['high_risk_detected_as_high_risk']}/{s['high_risk_total']} = "
          f"{s['high_risk_recall_collapsed']:.3f}  95% CI {s['high_risk_recall_ci95']}")
    print(f"  under-prediction rate {s['under_prediction_rate']:.3f} "
          f"(high-risk {s['under_prediction_rate_high_risk']:.3f}, "
          f"{s['severe_under_predictions_2plus_levels']} off by 2+ levels)")
    print(f"  max(ML,rules) high-risk recall: {c['high_risk_recall_collapsed']:.3f} "
          f"({ev['rows_rescued_by_rules']} rescued by the follow-up rule)")
