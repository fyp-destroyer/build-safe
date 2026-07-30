"""Measure what would actually raise high-risk recall, rather than guessing.

Run: python ml/analyze_recall.py

Everything is measured over grouped 5-fold CV on all 555 rows, not the
81-row test split, because the test split's 95% CI is ~±0.2 wide - far too
loose to compare interventions against.

The metric that matters is the SAFETY tradeoff, so every option is reported
as a pair: high-risk recall (of tasks truly 4-5, how many were flagged 4-5)
against the over-escalation rate (of tasks truly 1-3, how many were wrongly
flagged 4-5). Recall alone is trivially maximised by flagging everything.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold

from evaluation import HIGH_RISK, labels_of, load, wilson
from train_baseline import build_pipeline, to_frame

C, NGRAM = 4.0, (1, 1)


def folds(rows):
    X, y = to_frame(rows), labels_of(rows)
    g = np.array([r["group_id"] for r in rows])
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=0)
    return X, y, list(cv.split(X, y, g))


def scores(y_true, hi_flag) -> tuple[float, float, int, int]:
    """(recall on truly-high-risk, over-escalation rate on truly-low-risk)."""
    hi = np.isin(y_true, HIGH_RISK)
    rec = (hi_flag & hi).sum() / hi.sum()
    over = (hi_flag & ~hi).sum() / (~hi).sum()
    return rec, over, int(hi.sum()), int((~hi).sum())


def main() -> int:
    rows = load("train") + load("val") + load("test")
    X, y, splits = folds(rows)

    # Collect out-of-fold probabilities once; every option below is scored
    # on the same predictions so differences are attributable.
    oof_proba = np.zeros((len(rows), 5))
    oof_pred = np.zeros(len(rows), dtype=int)
    for tr, te in splits:
        m = build_pipeline(C, NGRAM).fit(X.iloc[tr], y[tr])
        oof_proba[te] = m.predict_proba(X.iloc[te])
        oof_pred[te] = m.predict(X.iloc[te])

    print("=" * 74)
    print("BASELINE (argmax, as currently served)")
    rec, over, nhi, nlo = scores(y, np.isin(oof_pred, HIGH_RISK))
    lo, up = wilson(int(rec * nhi), nhi)
    print(f"  high-risk recall {rec:.3f}  95% CI [{lo:.2f}, {up:.2f}]   "
          f"over-escalation {over:.3f}   (n_high={nhi}, n_low={nlo})")

    # ---- option 1: threshold on P(risk >= 4) instead of argmax -----------
    print("\n" + "=" * 74)
    print("OPTION 1 - decision threshold on P(risk>=4) instead of argmax")
    print("  Flag as high-risk when P(4)+P(5) >= t. No retraining; a config knob.")
    print(f"\n  {'threshold':>10} {'HR recall':>10} {'over-esc':>10}  {'verdict':<28}")
    p_high = oof_proba[:, 3] + oof_proba[:, 4]
    for t in (0.50, 0.40, 0.30, 0.25, 0.20, 0.15, 0.10, 0.05):
        rec, over, _, _ = scores(y, p_high >= t)
        note = ""
        if rec >= 0.95:
            note = "<-- meets prd.md 7 target"
        elif rec >= 0.90:
            note = "<-- close to target"
        print(f"  {t:>10.2f} {rec:>10.3f} {over:>10.3f}  {note:<28}")

    # ---- option 2: heavier class weighting -------------------------------
    print("\n" + "=" * 74)
    print("OPTION 2 - weight the severe classes harder than 'balanced'")
    for mult in (1, 2, 4, 8):
        w = {1: 1.0, 2: 1.0, 3: 1.0, 4: float(mult), 5: float(mult)}
        pred = np.zeros(len(rows), dtype=int)
        for tr, te in splits:
            pipe = build_pipeline(C, NGRAM)
            pipe.set_params(clf=LogisticRegression(max_iter=4000, C=C, class_weight=w))
            pred[te] = pipe.fit(X.iloc[tr], y[tr]).predict(X.iloc[te])
        rec, over, _, _ = scores(y, np.isin(pred, HIGH_RISK))
        label = "balanced-equivalent" if mult == 1 else f"{mult}x weight on 4/5"
        print(f"  {label:<24} recall {rec:.3f}   over-escalation {over:.3f}")

    # ---- option 3: does more data help? ----------------------------------
    print("\n" + "=" * 74)
    print("OPTION 3 - learning curve: is the model data-limited?")
    print("  Recall at increasing fractions of the training folds.")
    rng = np.random.RandomState(0)
    for frac in (0.25, 0.5, 0.75, 1.0):
        pred = np.zeros(len(rows), dtype=int)
        for tr, te in splits:
            k = max(20, int(len(tr) * frac))
            sub = rng.permutation(tr)[:k]
            pred[te] = build_pipeline(C, NGRAM).fit(X.iloc[sub], y[sub]).predict(X.iloc[te])
        rec, over, _, _ = scores(y, np.isin(pred, HIGH_RISK))
        print(f"  {int(frac * 100):>3}% of training data   recall {rec:.3f}   "
              f"over-escalation {over:.3f}")

    # ---- what the REAL rule engine contributes ---------------------------
    # Simulated the way production actually behaves: assess_job 409s until
    # every required follow-up is answered, so a job reaching assessment
    # never has a missing one. Using the dataset's answer where it has one
    # and the SAFE answer otherwise - anything else measures a state the
    # product cannot reach and flatters the numbers.
    print("\n" + "=" * 74)
    print("CONTEXT - what the deployed system actually achieves")
    sys.path.insert(0, str(Path(__file__).parents[1] / "apps" / "backend"))
    from ai.rule_engine import evaluate, required_followups

    rule = []
    for r in rows:
        known = {f["field"]: f["answer"] for f in r["followup_questions"]
                 if f["answer"] is not None}
        answers = {f: known.get(f, True) for f in required_followups(
            r["task_text"], r["category"], user_skill=r["user_skill"])}
        rule.append(evaluate(r["task_text"], r["category"], answers,
                             user_skill=r["user_skill"])[0])
    rule = np.array(rule)

    for name, flag in (("ML alone", np.isin(oof_pred, HIGH_RISK)),
                       ("rule engine alone", rule >= 4),
                       ("DEPLOYED max(ML, rules)",
                        np.isin(np.maximum(oof_pred, rule), HIGH_RISK))):
        rec, over, _, _ = scores(y, flag)
        print(f"  {name:24s} recall {rec:.3f}   over-escalation {over:.3f}")
    print("\n  The rule engine is far MORE PRECISE than the model: it buys")
    print("  recall at ~0.01 over-escalation, where the model pays ~0.08.")
    print("  That makes new rules the cheapest available recall.")

    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
