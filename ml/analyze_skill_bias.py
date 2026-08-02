"""Is `user_skill` a task-risk feature, or a leaked label?

Run: python ml/analyze_skill_bias.py

WHY THIS EXISTS
---------------
Observed live on 2026-08-01: the shipped baseline returns a different risk
level for the same task text depending only on `user_skill`, and in the wrong
direction — "change a light bulb" scores 1 for a Beginner and 4 for an
Experienced user, while "rewire the consumer unit" also scores 1 for a
Beginner. The prediction barely responds to the task at all.

The seed data chose `user_skill` "to fit the narrative" of each example (see
memory.md, 2026-07-29) — an experienced person is a plausible narrator for a
professional-tier job, a beginner for a simple one. That reasoning was
recorded and judged safe at the time. This script measures whether it was.

It changes nothing. It prints three things:
  1. the risk_level x user_skill contingency table
  2. logistic-regression coefficient mass on the skill columns vs the text
  3. a grouped-CV ablation: same pipeline, with and without `user_skill`

Read the ablation as the decision number. If dropping the feature costs
little or nothing, the model was reading the dropdown rather than the task,
and skill-based escalation belongs where it already is and is testable — the
rule engine (`Rule.requires_skill`, srs.md §9).
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from evaluation import labels_of, load, safety_metrics

SKILLS = ["Beginner", "Some experience", "Experienced"]


def to_frame(rows: list[dict], *, use_skill: bool):
    import pandas as pd

    data = {
        "task_text": [r["task_text"] for r in rows],
        "category": [r["category"] for r in rows],
    }
    if use_skill:
        data["user_skill"] = [r["user_skill"] for r in rows]
    return pd.DataFrame(data)


def build_pipeline(*, use_skill: bool, C: float = 4.0, ngram=(1, 2)) -> Pipeline:
    """The shipped baseline pipeline, with `user_skill` optionally removed.

    Everything else is held identical to ml/train_baseline.py so the ablation
    measures the feature and not a configuration difference.
    """
    cat_columns = ["category", "user_skill"] if use_skill else ["category"]
    return Pipeline(
        [
            (
                "features",
                ColumnTransformer(
                    [
                        (
                            "text",
                            TfidfVectorizer(
                                ngram_range=ngram,
                                sublinear_tf=True,
                                min_df=1,
                                strip_accents="unicode",
                            ),
                            "task_text",
                        ),
                        (
                            "char",
                            TfidfVectorizer(
                                analyzer="char_wb",
                                ngram_range=(3, 5),
                                sublinear_tf=True,
                                min_df=2,
                            ),
                            "task_text",
                        ),
                        ("cat", OneHotEncoder(handle_unknown="ignore"), cat_columns),
                    ]
                ),
            ),
            ("clf", LogisticRegression(max_iter=4000, C=C, class_weight="balanced")),
        ]
    )


def contingency(rows: list[dict]) -> None:
    print("\n" + "=" * 78)
    print("1. risk_level x user_skill  (the confound, if there is one)")
    print("=" * 78)
    header = f"{'':12}" + "".join(f"{s:>18}" for s in SKILLS) + f"{'total':>8}"
    print(header)
    for level in range(1, 6):
        counts = [
            sum(1 for r in rows if r["risk_level"] == level and r["user_skill"] == s)
            for s in SKILLS
        ]
        print(f"{'level ' + str(level):12}" + "".join(f"{c:>18}" for c in counts) + f"{sum(counts):>8}")
    totals = [sum(1 for r in rows if r["user_skill"] == s) for s in SKILLS]
    print(f"{'total':12}" + "".join(f"{t:>18}" for t in totals))

    print("\nWithin each skill value, how concentrated is the label?")
    for skill in SKILLS:
        levels = [r["risk_level"] for r in rows if r["user_skill"] == skill]
        if not levels:
            continue
        top_level, top_n = Counter(levels).most_common(1)[0]
        print(
            f"  {skill:18} n={len(levels):4}  mean={np.mean(levels):.2f}  "
            f"most common = level {top_level} ({100 * top_n / len(levels):.0f}% of its rows)"
        )
    print(
        "\n  A skill value whose rows are concentrated on one label is not a "
        "\n  feature describing the user - it is a proxy for the answer."
    )


def coefficient_mass(rows: list[dict]) -> None:
    print("\n" + "=" * 78)
    print("2. Where the model's weight actually sits")
    print("=" * 78)
    X, y = to_frame(rows, use_skill=True), labels_of(rows)
    model = build_pipeline(use_skill=True).fit(X, y)
    ct = model.named_steps["features"]
    coefs = model.named_steps["clf"].coef_  # (n_classes, n_features)

    spans, start = {}, 0
    for name, _, _ in ct.transformers_:
        width = len(ct.named_transformers_[name].get_feature_names_out())
        spans[name] = (start, start + width)
        start += width

    print(f"{'block':10}{'columns':>10}{'mean |coef|':>14}{'max |coef|':>14}")
    for name, (lo, hi) in spans.items():
        block = np.abs(coefs[:, lo:hi])
        print(f"{name:10}{hi - lo:>10}{block.mean():>14.4f}{block.max():>14.4f}")
    print(
        "\n  'cat' holds the one-hot category + skill columns. A handful of dense\n"
        "  columns carrying weight comparable to thousands of sparse text columns\n"
        "  means the text is being outvoted."
    )


def ablation(rows: list[dict]) -> None:
    print("\n" + "=" * 78)
    print("3. Ablation: grouped 5-fold CV, with and without user_skill")
    print("=" * 78)
    y = labels_of(rows)
    groups = np.array([r["group_id"] for r in rows])
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=0)

    for use_skill in (True, False):
        X = to_frame(rows, use_skill=use_skill)
        f1s, recalls = [], []
        for tr, te in cv.split(X, y, groups):
            model = build_pipeline(use_skill=use_skill).fit(X.iloc[tr], y[tr])
            pred = model.predict(X.iloc[te])
            f1s.append(f1_score(y[te], pred, average="macro", zero_division=0))
            s = safety_metrics(y[te], pred)
            if s["high_risk_recall_collapsed"] is not None:
                recalls.append(s["high_risk_recall_collapsed"])
        label = "WITH user_skill" if use_skill else "WITHOUT user_skill"
        print(
            f"  {label:20} macro-F1 {np.mean(f1s):.3f} +/- {np.std(f1s):.3f}   "
            f"high-risk recall {np.mean(recalls):.3f} +/- {np.std(recalls):.3f}"
        )


def responsiveness(rows: list[dict]) -> None:
    """Does the prediction move with the TASK, holding skill fixed?

    This is the property the live report was really about: a safety
    classifier that answers the same for "rewire the consumer unit" and
    "assemble a flat pack wardrobe" is not classifying the task.
    """
    print("\n" + "=" * 78)
    print("4. Does the prediction respond to the task text?")
    print("=" * 78)
    probes = [
        ("change a burnt out light bulb in the kitchen", "electrical"),
        ("assemble a flat pack wardrobe", "carpentry"),
        ("paint a bedroom wall with a roller", "painting"),
        ("rewire the consumer unit in my garage", "electrical"),
        ("I can smell gas near the cooker connection", "plumbing"),
    ]
    for use_skill in (True, False):
        X, y = to_frame(rows, use_skill=use_skill), labels_of(rows)
        model = build_pipeline(use_skill=use_skill).fit(X, y)
        print(f"\n  {'WITH user_skill' if use_skill else 'WITHOUT user_skill'}")
        header = f"    {'task':46}" + ("".join(f"{s[:11]:>13}" for s in SKILLS) if use_skill else f"{'predicted':>13}")
        print(header)
        for text, category in probes:
            if use_skill:
                preds = []
                for skill in SKILLS:
                    frame = to_frame(
                        [{"task_text": text, "category": category, "user_skill": skill}],
                        use_skill=True,
                    )
                    preds.append(int(model.predict(frame)[0]))
                cells = "".join(f"{p:>13}" for p in preds)
            else:
                frame = to_frame(
                    [{"task_text": text, "category": category, "user_skill": "Beginner"}],
                    use_skill=False,
                )
                cells = f"{int(model.predict(frame)[0]):>13}"
            print(f"    {text[:46]:46}{cells}")


def main() -> int:
    rows = load("train") + load("val") + load("test")
    print(f"loaded {len(rows)} rows from ml/data/{{train,val,test}}.json")
    contingency(rows)
    coefficient_mass(rows)
    ablation(rows)
    responsiveness(rows)
    print("\nNothing was written. This script only measures.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
