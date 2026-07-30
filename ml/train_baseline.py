"""Phase 3: baseline risk classifier - TF-IDF + Logistic Regression.

Run: python ml/train_baseline.py

Writes:
  ml/eval/baseline_model.joblib     fitted pipeline (refit on train+val)
  ml/eval/baseline_report.md        human-readable evaluation report
  ml/eval/baseline_metrics.json     same numbers, machine-readable
  ml/eval/baseline_confusion.png    confusion matrix on the test split

FEATURES ARE DELIBERATELY RESTRICTED to what the backend actually knows
when a user submits a job (architecture.md 4, srs.md 8):

    task_text, category, user_skill

NOT tools_available. The dataset records it, but the backend has no such
field - `Job` stores description/category/skill_level/urgency and nothing
about tools, and the conversational intake never asks. Training on a feature
production cannot supply is train/serve skew: measured on this data, a model
fitted with tools scores macro-F1 0.613 but drops to 0.549 when served with
tools blanked, because 87% of training rows have them and it leans on them.
So the shipped model is fitted WITHOUT tools and its reported numbers are
what it will actually deliver in production. Restore the feature only if
`Job` gains a tools column and intake starts collecting it.

Everything else in a dataset row is an OUTPUT of the assessment, and using
it would leak the label. Measured on the current data:

    professional_category is None  <=> risk_level <= 2   (exactly, 555/555)
    suggested_ppe == []            <=  risk_level == 5   (always)
    unanswered safety followup     =>  risk_level == 5   (all 59 rows)
    37 of 66 distinct hazard sets map to exactly one risk level

The follow-up state is excluded for a second reason: "unanswered
safety-critical follow-up => risk 5" is the RULE ENGINE's job
(ai/rule_engine/), and final_risk = max(ML, rules) combines them. Feeding
it to the classifier would just make the ML half relearn the rule half and
report a flattering number for work the rules already do. The classifier's
job here is to judge risk from the user's own description.

NOTE ON THE HEADLINE NUMBERS: metrics are reported on the hand-written
subset of the test split as well as the full split. Generated rows are
weakly labelled paraphrases of their parents, so scores over them partly
measure the generator (see ml/data/README.md).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import joblib
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from evaluation import (EVAL, RISK_NAMES, confusion_table, evaluate_predictions,
                        labels_of, load, per_class_table, plot_confusion,
                        print_summary, safety_metrics)

EVAL.mkdir(exist_ok=True)


# --------------------------------------------------------------------------
def to_frame(rows: list[dict]):
    import pandas as pd
    return pd.DataFrame({
        "task_text": [r["task_text"] for r in rows],
        "category": [r["category"] for r in rows],
        "user_skill": [r["user_skill"] for r in rows],
        # NOTE: tools_available is deliberately NOT a feature - the backend
        # cannot supply it at inference time. See the module docstring.
    })


def build_pipeline(C: float, ngram: tuple[int, int]) -> Pipeline:
    return Pipeline([
        ("features", ColumnTransformer([
            ("text", TfidfVectorizer(ngram_range=ngram, sublinear_tf=True,
                                     min_df=1, strip_accents="unicode"), "task_text"),
            # Char n-grams help a lot on a few-hundred-row corpus: they pick up
            # shared morphology ("wiring"/"rewire") that word n-grams miss.
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                     sublinear_tf=True, min_df=2), "task_text"),
            ("cat", OneHotEncoder(handle_unknown="ignore"), ["category", "user_skill"]),
        ])),
        ("clf", LogisticRegression(
            max_iter=4000, C=C,
            # Under-predicting risk is the failure mode that matters
            # (prd.md 7). Balanced weighting stops the model favouring the
            # larger low-risk classes at the expense of 4/5 recall.
            class_weight="balanced")),
    ])


# --------------------------------------------------------------------------
def main() -> int:
    train, val, test = load("train"), load("val"), load("test")
    Xtr, ytr = to_frame(train), labels_of(train)
    Xva, yva = to_frame(val), labels_of(val)

    # ---- hyperparameter selection on val (never on test)
    grid = [(C, ng) for C in (0.5, 1.0, 4.0, 10.0) for ng in ((1, 1), (1, 2))]
    results = []
    for C, ng in grid:
        m = build_pipeline(C, ng).fit(Xtr, ytr)
        pv = m.predict(Xva)
        results.append((f1_score(yva, pv, average="macro", zero_division=0), C, ng))
    results.sort(reverse=True)
    best_f1, best_C, best_ng = results[0]
    print(f"selected on val: C={best_C} ngram={best_ng} (macro-F1 {best_f1:.3f})")

    # ---- test evaluation, trained on train only (val untouched by fitting)
    model = build_pipeline(best_C, best_ng).fit(Xtr, ytr)
    seed_test = [r for r in test if r["source"] == "seed"]
    ev_full = evaluate_predictions("test (all rows)", test, model.predict(to_frame(test)))
    ev_seed = evaluate_predictions("test (hand-written only)", seed_test,
                                   model.predict(to_frame(seed_test)))

    # ---- grouped CV over everything: a single 82-row test split is thin, and
    # grouping keeps a seed and its variants on the same side of every fold.
    all_rows = train + val + test
    Xall, yall = to_frame(all_rows), labels_of(all_rows)
    groups = np.array([r["group_id"] for r in all_rows])
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=0)
    fold_f1, fold_hi = [], []
    for tr_i, te_i in cv.split(Xall, yall, groups):
        m = build_pipeline(best_C, best_ng).fit(Xall.iloc[tr_i], yall[tr_i])
        p = m.predict(Xall.iloc[te_i])
        fold_f1.append(f1_score(yall[te_i], p, average="macro", zero_division=0))
        s = safety_metrics(yall[te_i], p)
        if s["high_risk_recall_collapsed"] is not None:
            fold_hi.append(s["high_risk_recall_collapsed"])
    cv_summary = {
        "folds": 5,
        "macro_f1_mean": float(np.mean(fold_f1)),
        "macro_f1_std": float(np.std(fold_f1)),
        "high_risk_recall_mean": float(np.mean(fold_hi)),
        "high_risk_recall_std": float(np.std(fold_hi)),
    }

    # ---- artifact: refit on train+val so the shipped model uses all the
    # data it legitimately can. Test stays held out.
    import pandas as pd
    final = build_pipeline(best_C, best_ng).fit(
        pd.concat([Xtr, Xva], ignore_index=True), np.concatenate([ytr, yva]))
    joblib.dump({"model": final, "C": best_C, "ngram": best_ng,
                 "features": ["task_text", "category", "user_skill"],
                 "risk_levels": [1, 2, 3, 4, 5]},
                EVAL / "baseline_model.joblib")

    metrics = {"selected": {"C": best_C, "ngram": list(best_ng), "val_macro_f1": best_f1},
               "test_all": ev_full, "test_handwritten": ev_seed, "grouped_cv": cv_summary}
    (EVAL / "baseline_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    write_report(metrics, test, seed_test)
    plot_confusion(ev_full["confusion"], EVAL / "baseline_confusion.png",
                   "Baseline confusion matrix - test split")

    # ---- console summary
    for ev in (ev_full, ev_seed):
        print_summary(ev)
    print(f"\ngrouped 5-fold CV: macro-F1 {cv_summary['macro_f1_mean']:.3f}"
          f" +/- {cv_summary['macro_f1_std']:.3f}   "
          f"high-risk recall {cv_summary['high_risk_recall_mean']:.3f}"
          f" +/- {cv_summary['high_risk_recall_std']:.3f}")
    print(f"\nwrote {EVAL}/baseline_model.joblib, baseline_report.md, "
          f"baseline_metrics.json, baseline_confusion.png")
    return 0


# --------------------------------------------------------------------------
def write_report(m: dict, test: list[dict], seed_test: list[dict]) -> None:
    def table(ev: dict) -> str:
        out = ["| risk level | precision | recall | F1 | support |",
               "|---|---|---|---|---|"]
        for i in range(1, 6):
            r = ev["per_class"][RISK_NAMES[i]]
            out.append(f"| {i} — {RISK_NAMES[i]} | {r['precision']:.2f} | "
                       f"{r['recall']:.2f} | {r['f1-score']:.2f} | {int(r['support'])} |")
        return "\n".join(out)

    def cm_table(ev: dict) -> str:
        out = ["| true \\ pred | 1 | 2 | 3 | 4 | 5 |", "|---|---|---|---|---|---|"]
        for i, row in enumerate(ev["confusion"], 1):
            out.append(f"| **{i}** | " + " | ".join(str(v) for v in row) + " |")
        return "\n".join(out)

    fa, fs, cv = m["test_all"], m["test_handwritten"], m["grouped_cv"]
    sa, ss = fa["safety"], fs["safety"]
    doc = f"""# Baseline Model — Evaluation Report (Phase 3)

TF-IDF + Logistic Regression. Reproduce with `python ml/train_baseline.py`.
Selected on the validation split: `C={m['selected']['C']}`,
word n-grams `{tuple(m['selected']['ngram'])}` (val macro-F1 {m['selected']['val_macro_f1']:.3f}).

## Features — and what was deliberately excluded

Inputs are limited to what the backend actually has at assessment time:
`task_text`, `category`, `user_skill`.

`tools_available` is in the dataset but is **not** a feature: the backend has
no tools column and intake never asks, so training on it would be train/serve
skew. Fitting with it scored macro-F1 0.613, but serving it blanked — which is
all production could ever do — dropped that to 0.549. The numbers below are
therefore what the model will actually deliver.

Every other field in a row is an **output** of the assessment and would leak the
label. This is not a theoretical concern — measured on the 555 rows:

| Field | Relationship to the label |
|---|---|
| `professional_category` | `is None` ⟺ `risk_level <= 2`, exactly, 555/555 rows |
| `suggested_ppe` | `== []` whenever `risk_level == 5` |
| `followup_questions` | an unanswered safety-critical follow-up ⟹ `risk_level == 5`, all 59 rows |
| `hazards` | 37 of 66 distinct hazard sets map to exactly one risk level |

Follow-up state is excluded for a second reason: escalating on a missing
safety-critical answer is the **rule engine's** job, and `final_risk = max(ML,
rules)` combines the two. Feeding it here would make the ML half relearn the
rule half and report a flattering number for work the rules already do.

## Headline results

Metrics on generated rows partly measure the paraphrase generator rather than
the task, so the hand-written subset is the number to trust.

| | test (all {fa['n']}) | test (hand-written {fs['n']}) |
|---|---|---|
| accuracy | {fa['accuracy']:.3f} | {fs['accuracy']:.3f} |
| macro F1 | {fa['macro_f1']:.3f} | {fs['macro_f1']:.3f} |
| high-risk recall (≥4 caught as ≥4) | {sa['high_risk_recall_collapsed']:.3f} | {ss['high_risk_recall_collapsed']:.3f} |
| 95% CI on that recall | {sa['high_risk_recall_ci95']} | {ss['high_risk_recall_ci95']} |
| under-prediction rate (all) | {sa['under_prediction_rate']:.3f} | {ss['under_prediction_rate']:.3f} |
| under-prediction rate (high-risk) | {sa['under_prediction_rate_high_risk']:.3f} | {ss['under_prediction_rate_high_risk']:.3f} |
| under-predicted by ≥2 levels | {sa['severe_under_predictions_2plus_levels']} | {ss['severe_under_predictions_2plus_levels']} |

### The classifier is not the whole safety story

The system ships `final_risk = max(ML, rules)` (`architecture.md` §2, `srs.md` §8.1),
and the classifier is deliberately blind to follow-up state so the rule engine
can own that escalation. **ML-only recall therefore understates the deployed
system.** Simulating just the "unanswered safety-critical follow-up ⟹ 5" rule
on top of these predictions:

| | ML alone | max(ML, rules) |
|---|---|---|
| high-risk recall, test (all) | {sa['high_risk_recall_collapsed']:.3f} | **{fa['safety_combined_with_rules']['high_risk_recall_collapsed']:.3f}** |
| high-risk recall, hand-written | {ss['high_risk_recall_collapsed']:.3f} | **{fs['safety_combined_with_rules']['high_risk_recall_collapsed']:.3f}** |
| high-risk rows rescued by the rule | — | {fa['rows_rescued_by_rules']} |

That is still a floor, not a ceiling: only the follow-up rule is simulated here.
The real engine also carries keyword hazard rules, so the deployed system
escalates strictly more than this table shows.

### Grouped 5-fold cross-validation (all 555 rows)

A single 82-row test split is thin. This CV groups by `group_id`, so a seed and
its variants never straddle a fold — it is the more stable estimate.

- macro F1 **{cv['macro_f1_mean']:.3f} ± {cv['macro_f1_std']:.3f}**
- high-risk recall **{cv['high_risk_recall_mean']:.3f} ± {cv['high_risk_recall_std']:.3f}**

## Why "high-risk recall" is reported collapsed

Per-class recall punishes predicting 5 when the truth is 4, which is not a
safety failure — the system escalates and the user is told to get a
professional. What matters is whether a genuinely dangerous task is *recognised
as* dangerous. So the headline number is: of tasks truly at level 4–5, what
fraction were predicted at 4–5. The **under-prediction rate** is the direct
measure of the failure mode `prd.md` §7 targets.

## Per-class detail — test (all rows)

{table(fa)}

### Confusion matrix — test (all rows)

{cm_table(fa)}

![confusion matrix](baseline_confusion.png)

## Per-class detail — test (hand-written only)

{table(fs)}

## Limitations

1. **Small test set.** {fs['n']} hand-written rows; high-risk recall rests on
   {ss['high_risk_total']} examples. The confidence interval above is wide — quote it,
   not the point estimate.
2. **Weak labels in training.** 299 of 555 rows are generated paraphrases
   inheriting a parent's label, so effective sample size is well below 555.
3. **Label ceiling.** `ml/data/REVIEW.md` records that labels were
   standards-audited but never reviewed by a domain expert. The model cannot be
   more correct than its labels.
4. **No calibration.** Predicted probabilities are unvalidated; `srs.md` stores a
   confidence with each assessment, so calibration should be checked before that
   value is shown to users or used for thresholding.
5. **This is a baseline.** Phase 4 compares it against sentence-embedding
   features; the decision on which ships is recorded there.

## Phase 3 exit check

> "baseline recall on high-risk classes measured and documented (even if not yet at target)"

Measured and documented above. Target for reference (`prd.md` §7, provisional):
≥95% recall on the two most severe classes.
"""
    (EVAL / "baseline_report.md").write_text(doc, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
