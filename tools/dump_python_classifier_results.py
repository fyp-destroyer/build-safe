"""Run the PYTHON classifier over every dataset row and dump its predictions.

Half of the classifier port equivalence gate; tools/compare_classifiers.mjs runs
the TypeScript port over the same rows and diffs against this output.

Probabilities are dumped, not just the predicted class. Two implementations can
agree on the argmax while disagreeing badly underneath — a char n-gram window
that is off by one still picks the same winner most of the time, and would show
up as an occasional, unexplainable misclassification months later. Comparing the
full probability vector catches that immediately.

MUST BE RUN WITH THE PINNED SCIKIT-LEARN (1.8.0, see ml/requirements.txt), since
that is the version the artifact was fitted and pickled with.

USAGE
    python tools/dump_python_classifier_results.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "ml" / "eval" / "baseline_model.joblib"
DATA = ROOT / "ml" / "data"
OUT = ROOT / "tools" / "classifier_python_results.json"


def load_rows() -> list[dict]:
    rows: list[dict] = []
    for name in ("seed_examples.json", "generated_examples.json", "holdout_rules.json"):
        path = DATA / name
        if not path.exists():
            continue
        for item in json.loads(path.read_text(encoding="utf-8")):
            rows.append(
                {
                    "task_text": item["task_text"],
                    "category": item.get("category", "general"),
                }
            )

    seen: set[tuple[str, str]] = set()
    unique = []
    for r in rows:
        key = (r["task_text"], r["category"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique


def main() -> int:
    import sklearn

    print(f"scikit-learn {sklearn.__version__}")
    if sklearn.__version__ != "1.8.0":
        print(
            "  WARNING: ml/requirements.txt pins 1.8.0, which is the version the "
            "artifact was pickled with. Results may not be authoritative.",
            file=sys.stderr,
        )

    bundle = joblib.load(MODEL_PATH)
    model = bundle["model"]
    classes = [int(c) for c in model.named_steps["clf"].classes_]

    rows = load_rows()
    X = pd.DataFrame(
        {
            "task_text": [r["task_text"] for r in rows],
            "category": [r["category"] for r in rows],
        }
    )

    proba = model.predict_proba(X)
    pred = model.predict(X)

    results = [
        {
            "task_text": r["task_text"],
            "category": r["category"],
            "predicted": int(pred[i]),
            "probabilities": [float(p) for p in proba[i]],
        }
        for i, r in enumerate(rows)
    ]

    OUT.write_text(
        json.dumps({"classes": classes, "rows": results}, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"wrote {OUT}")
    print(f"  {len(results)} rows, classes={classes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
