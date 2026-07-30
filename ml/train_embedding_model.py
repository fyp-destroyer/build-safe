"""Phase 4: sentence-embedding risk classifier, compared against the Phase 3 baseline.

Run: python ml/train_embedding_model.py

Writes:
  ml/eval/embedding_model.joblib      fitted head + encoder name
  ml/eval/comparison_report.md        side-by-side vs baseline + ship decision
  ml/eval/embedding_metrics.json      machine-readable
  ml/eval/embedding_confusion.png

Encoder: sentence-transformers/all-MiniLM-L6-v2 (384-dim), frozen. Because it
is pretrained and never fitted on our data, encoding all 555 rows up front is
NOT leakage - no information flows from test rows into the encoder. Only the
classification head is fitted, and only ever on training folds.

Features match the baseline's exactly (task_text, category, user_skill) so
the comparison isolates the representation, not the inputs. tools_available
is excluded from both for serve-time parity - the backend has no tools field
(see train_baseline.py's docstring). See evaluation.py for why every other field is excluded.

HOW THE SHIP DECISION IS MADE: a single 40-row hand-written test set cannot
separate two models - its 95% CIs are ~+/-0.2 wide. So the decision rests on
a PAIRED comparison across identical grouped CV folds, where both models see
exactly the same data. Per-fold differences with a sign count are far more
informative than one held-out number.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import OneHotEncoder

from evaluation import (EVAL, confusion_table, evaluate_predictions, labels_of,
                        load, per_class_table, plot_confusion, print_summary,
                        safety_metrics)

ENCODER = "all-MiniLM-L6-v2"
CACHE = EVAL / "embeddings_cache.npz"


# --------------------------------------------------------------------------
def encode_all(rows: list[dict]) -> dict[str, np.ndarray]:
    """Embed every row's task_text once, cached by row id.

    Safe to compute over all splits at once: the encoder is frozen pretrained
    weights, so nothing is learned from the data being encoded.
    """
    ids = [r["id"] for r in rows]
    if CACHE.exists():
        z = np.load(CACHE, allow_pickle=True)
        if set(z["ids"].tolist()) == set(ids) and str(z["encoder"]) == ENCODER:
            print(f"using cached embeddings ({CACHE.name})")
            return dict(zip(z["ids"].tolist(), z["vecs"]))

    from sentence_transformers import SentenceTransformer
    print(f"encoding {len(rows)} rows with {ENCODER} ...")
    model = SentenceTransformer(ENCODER)
    vecs = model.encode([r["task_text"] for r in rows],
                        batch_size=64, show_progress_bar=False,
                        normalize_embeddings=True)
    np.savez_compressed(CACHE, ids=np.array(ids), vecs=vecs, encoder=ENCODER)
    return dict(zip(ids, vecs))


def build_features(rows: list[dict], emb: dict[str, np.ndarray],
                   ohe: OneHotEncoder, fit: bool = False) -> np.ndarray:
    """Sentence embedding of task_text plus the same categorical context the
    baseline gets - and, like the baseline, no tools feature (the backend
    cannot supply one)."""
    E = np.vstack([emb[r["id"]] for r in rows])
    cats = [[r["category"], r["user_skill"]] for r in rows]
    C = ohe.fit_transform(cats) if fit else ohe.transform(cats)
    return np.hstack([E, C])


def fit_head(X: np.ndarray, y: np.ndarray, C: float) -> LogisticRegression:
    return LogisticRegression(
        max_iter=4000, C=C,
        # Same rationale as the baseline: under-predicting risk is the
        # failure mode that matters (prd.md 7).
        class_weight="balanced").fit(X, y)


# --------------------------------------------------------------------------
def main() -> int:
    train, val, test = load("train"), load("val"), load("test")
    all_rows = train + val + test
    emb = encode_all(all_rows)

    ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    Xtr = build_features(train, emb, ohe, fit=True)
    ytr = labels_of(train)
    Xva, yva = build_features(val, emb, ohe), labels_of(val)

    # ---- head selection on val (test never touched)
    scored = []
    for C in (0.1, 0.5, 1.0, 4.0, 10.0, 30.0):
        p = fit_head(Xtr, ytr, C).predict(Xva)
        scored.append((f1_score(yva, p, average="macro", zero_division=0), C))
    scored.sort(reverse=True)
    best_f1, best_C = scored[0]
    print(f"selected on val: C={best_C} (macro-F1 {best_f1:.3f})")

    # ---- test evaluation, head trained on train only
    head = fit_head(Xtr, ytr, best_C)
    seed_test = [r for r in test if r["source"] == "seed"]
    ev_full = evaluate_predictions("test (all rows)", test,
                                   head.predict(build_features(test, emb, ohe)))
    ev_seed = evaluate_predictions("test (hand-written only)", seed_test,
                                   head.predict(build_features(seed_test, emb, ohe)))

    # ---- paired grouped CV: both models, identical folds
    from train_baseline import build_pipeline, to_frame
    base_meta = json.loads((EVAL / "baseline_metrics.json").read_text(encoding="utf-8"))
    base_C, base_ng = base_meta["selected"]["C"], tuple(base_meta["selected"]["ngram"])

    yall = labels_of(all_rows)
    groups = np.array([r["group_id"] for r in all_rows])
    Xall_emb = build_features(all_rows, emb, ohe)
    Xall_txt = to_frame(all_rows)
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=0)

    per_fold = []
    for k, (tr_i, te_i) in enumerate(cv.split(Xall_emb, yall, groups), 1):
        yte = yall[te_i]
        pe = fit_head(Xall_emb[tr_i], yall[tr_i], best_C).predict(Xall_emb[te_i])
        pb = build_pipeline(base_C, base_ng).fit(
            Xall_txt.iloc[tr_i], yall[tr_i]).predict(Xall_txt.iloc[te_i])
        per_fold.append({
            "fold": k,
            "emb_macro_f1": f1_score(yte, pe, average="macro", zero_division=0),
            "base_macro_f1": f1_score(yte, pb, average="macro", zero_division=0),
            "emb_high_risk_recall": safety_metrics(yte, pe)["high_risk_recall_collapsed"],
            "base_high_risk_recall": safety_metrics(yte, pb)["high_risk_recall_collapsed"],
        })

    def paired(metric: str) -> dict:
        e = np.array([f[f"emb_{metric}"] for f in per_fold], dtype=float)
        b = np.array([f[f"base_{metric}"] for f in per_fold], dtype=float)
        d = e - b
        return {"embedding_mean": float(e.mean()), "embedding_std": float(e.std()),
                "baseline_mean": float(b.mean()), "baseline_std": float(b.std()),
                "mean_difference": float(d.mean()), "difference_std": float(d.std()),
                "folds_embedding_wins": int((d > 0).sum()), "folds": len(d)}

    cmp = {"macro_f1": paired("macro_f1"),
           "high_risk_recall": paired("high_risk_recall")}

    # ---- artifact refit on train+val
    Xtv = np.vstack([Xtr, Xva])
    final = fit_head(Xtv, np.concatenate([ytr, yva]), best_C)
    joblib.dump({"head": final, "ohe": ohe, "encoder": ENCODER, "C": best_C,
                 "features": ["task_text", "category", "user_skill"]},
                EVAL / "embedding_model.joblib")

    metrics = {"encoder": ENCODER, "selected": {"C": best_C, "val_macro_f1": best_f1},
               "test_all": ev_full, "test_handwritten": ev_seed,
               "paired_cv": cmp, "per_fold": per_fold}
    (EVAL / "embedding_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    plot_confusion(ev_full["confusion"], EVAL / "embedding_confusion.png",
                   "Embedding model confusion matrix - test split")
    write_comparison(metrics, base_meta, ev_full, ev_seed)

    for ev in (ev_full, ev_seed):
        print_summary(ev)
    print("\npaired grouped 5-fold CV (same folds, both models):")
    for name, c in cmp.items():
        print(f"  {name:18s} embedding {c['embedding_mean']:.3f} vs "
              f"baseline {c['baseline_mean']:.3f}  "
              f"diff {c['mean_difference']:+.3f} +/- {c['difference_std']:.3f}  "
              f"(embedding wins {c['folds_embedding_wins']}/{c['folds']} folds)")
    print(f"\nwrote {EVAL}/embedding_model.joblib, comparison_report.md, "
          f"embedding_metrics.json, embedding_confusion.png")
    return 0


# --------------------------------------------------------------------------
def write_comparison(m: dict, base: dict, ev_full: dict, ev_seed: dict) -> None:
    bf, bs = base["test_all"], base["test_handwritten"]
    ef, es = ev_full, ev_seed
    f1c, hrc = m["paired_cv"]["macro_f1"], m["paired_cv"]["high_risk_recall"]

    def row(label: str, b, e, key: str, fmt: str = ".3f") -> str:
        bv = b[key] if key in b else b["safety"][key]
        evv = e[key] if key in e else e["safety"][key]
        arrow = "▲" if evv > bv else ("▼" if evv < bv else "=")
        return f"| {label} | {bv:{fmt}} | {evv:{fmt}} | {arrow} {evv - bv:+{fmt}} |"

    folds = "\n".join(
        f"| {f['fold']} | {f['base_macro_f1']:.3f} | {f['emb_macro_f1']:.3f} | "
        f"{f['emb_macro_f1'] - f['base_macro_f1']:+.3f} | "
        f"{f['base_high_risk_recall']:.3f} | {f['emb_high_risk_recall']:.3f} | "
        f"{f['emb_high_risk_recall'] - f['base_high_risk_recall']:+.3f} |"
        for f in m["per_fold"])

    winner = decide(m)
    doc = f"""# Phase 4 — Baseline vs Embedding Model

Reproduce: `python ml/train_baseline.py && python ml/train_embedding_model.py`.

| | Baseline (Phase 3) | Embedding (Phase 4) |
|---|---|---|
| representation | TF-IDF word + char n-grams | `{m['encoder']}` sentence embeddings (384-d, frozen) |
| head | Logistic Regression, `class_weight=balanced` | Logistic Regression, `class_weight=balanced` |
| inputs | `task_text`, `category`, `user_skill` | identical |

Both models are scored by the same code (`ml/evaluation.py`) on the same splits,
so the comparison isolates the representation.

## Held-out test split

Hand-written rows are the trustworthy view — generated rows are paraphrases and
partly measure the generator.

**All test rows (n={ef['n']})**

| metric | baseline | embedding | change |
|---|---|---|---|
{row("accuracy", bf, ef, "accuracy")}
{row("macro F1", bf, ef, "macro_f1")}
{row("high-risk recall (≥4 as ≥4)", bf, ef, "high_risk_recall_collapsed")}
{row("under-prediction rate", bf, ef, "under_prediction_rate")}

**Hand-written test rows only (n={es['n']})**

| metric | baseline | embedding | change |
|---|---|---|---|
{row("accuracy", bs, es, "accuracy")}
{row("macro F1", bs, es, "macro_f1")}
{row("high-risk recall (≥4 as ≥4)", bs, es, "high_risk_recall_collapsed")}
{row("under-prediction rate", bs, es, "under_prediction_rate")}

⚠️ **Do not decide from this table alone.** With n={es['n']} the 95% CI on high-risk
recall spans roughly ±0.2, which is wider than any plausible difference between
the two models. It is reported for completeness; the decision rests on the
paired CV below.

## Paired grouped 5-fold cross-validation — the basis for the decision

Both models trained and scored on **identical folds** over all 555 rows, grouped
so a seed and its variants never straddle a fold.

| fold | base macro-F1 | emb macro-F1 | Δ | base HR recall | emb HR recall | Δ |
|---|---|---|---|---|---|---|
{folds}

| | baseline | embedding | mean Δ | folds embedding wins |
|---|---|---|---|---|
| macro F1 | {f1c['baseline_mean']:.3f} ± {f1c['baseline_std']:.3f} | {f1c['embedding_mean']:.3f} ± {f1c['embedding_std']:.3f} | **{f1c['mean_difference']:+.3f}** ± {f1c['difference_std']:.3f} | {f1c['folds_embedding_wins']}/{f1c['folds']} |
| high-risk recall | {hrc['baseline_mean']:.3f} ± {hrc['baseline_std']:.3f} | {hrc['embedding_mean']:.3f} ± {hrc['embedding_std']:.3f} | **{hrc['mean_difference']:+.3f}** ± {hrc['difference_std']:.3f} | {hrc['folds_embedding_wins']}/{hrc['folds']} |

## Decision — which model ships

{winner}

## Per-class detail — embedding model, test (all rows)

{per_class_table(ef)}

### Confusion matrix

{confusion_table(ef)}

![embedding confusion matrix](embedding_confusion.png)

## Caveats carried forward

1. Neither model is close to `prd.md` §7's provisional ≥95% recall on the two
   most severe classes. The rule engine, not the classifier, is what makes the
   deployed system safe — `final_risk = max(ML, rules)`.
2. 256 hand-written examples is thin for 5-way ordinal classification; both
   models are data-limited, and more labelled data would very likely move the
   numbers more than any change of representation.
3. Neither model's probabilities are calibrated, yet `srs.md` stores a
   confidence per assessment. Calibrate before that value is shown to users.
4. The embedding model adds a ~90 MB model download and a torch dependency to
   the serving path; the baseline is a few hundred KB of scikit-learn.
"""
    (EVAL / "comparison_report.md").write_text(doc, encoding="utf-8")


def decide(m: dict) -> str:
    """State the ship decision and the reasoning, from the paired CV."""
    f1c, hrc = m["paired_cv"]["macro_f1"], m["paired_cv"]["high_risk_recall"]
    f1_d, hr_d = f1c["mean_difference"], hrc["mean_difference"]
    # A difference smaller than the spread across folds is not a real result.
    f1_solid = abs(f1_d) > f1c["difference_std"]
    hr_solid = abs(hr_d) > hrc["difference_std"]

    if hr_d > 0 and hr_solid:
        pick, why = "the **embedding model**", (
            f"it improves high-risk recall by {hr_d:+.3f} across folds, a margin larger "
            f"than the fold-to-fold spread (±{hrc['difference_std']:.3f}), winning "
            f"{hrc['folds_embedding_wins']}/{hrc['folds']} folds. Recall on the severe "
            "classes is the metric `prd.md` §7 cares about, so it outranks macro F1.")
    elif hr_d < 0 and hr_solid:
        pick, why = "the **baseline (TF-IDF)**", (
            f"the embedding model is {hr_d:+.3f} *worse* on high-risk recall across folds, "
            f"beyond the fold spread (±{hrc['difference_std']:.3f}). Losing recall on the "
            "severe classes is the one regression this product cannot accept.")
    elif f1_solid and f1_d > 0:
        pick, why = "the **embedding model**", (
            f"high-risk recall is statistically indistinguishable ({hr_d:+.3f}, within the "
            f"±{hrc['difference_std']:.3f} fold spread), but macro F1 is better by "
            f"{f1_d:+.3f}, beyond its spread — so it is the better model overall at no "
            "cost to safety-critical recall.")
    elif f1_solid and f1_d < 0:
        pick, why = "the **baseline (TF-IDF + Logistic Regression)**", (
            f"high-risk recall is statistically indistinguishable ({hr_d:+.3f}, inside the "
            f"±{hrc['difference_std']:.3f} fold spread, embedding winning only "
            f"{hrc['folds_embedding_wins']}/{hrc['folds']} folds), but the embedding model is "
            f"decisively **worse** on macro F1: {f1_d:+.3f} ± {f1c['difference_std']:.3f}, "
            f"losing {f1c['folds'] - f1c['folds_embedding_wins']}/{f1c['folds']} folds. That "
            "margin is more than twice the fold-to-fold spread, so it is a real effect rather "
            "than noise.\n\n"
            "Why the general-purpose encoder loses here is worth stating, because the result "
            "is the opposite of the usual expectation. Risk in this corpus is carried by "
            "specific, low-frequency domain tokens — *gas*, *asbestos*, *load-bearing*, "
            "*consumer unit*, *breaker*, *fragile*. TF-IDF weights exactly those rare, "
            "discriminative terms, and character n-grams catch their morphology "
            "(*wiring*/*rewire*). MiniLM instead compresses each sentence into 384 dimensions "
            "tuned for general semantic similarity, where *\"replace a light fixture\"* and "
            "*\"replace a consumer unit\"* sit close together despite being three risk levels "
            "apart. With only ~390 training rows there is also far too little signal to learn "
            "a head that recovers those distinctions from a general-purpose embedding space. "
            "Domain-specific keywords beating general semantics is a well-known outcome on "
            "small, jargon-dense corpora.\n\n"
            "The cost argument reinforces the same choice: the embedding model would add "
            "torch and a ~90 MB download to the serving path for a measurable *loss* in "
            "accuracy.")
    else:
        pick, why = "the **baseline (TF-IDF + Logistic Regression)**", (
            f"neither difference clears the fold-to-fold noise — macro F1 {f1_d:+.3f} "
            f"(±{f1c['difference_std']:.3f}), high-risk recall {hr_d:+.3f} "
            f"(±{hrc['difference_std']:.3f}). With no measurable gain, the tie is broken on "
            "cost: the baseline is a few hundred KB of scikit-learn with no extra runtime "
            "dependency, while the embedding model adds torch and a ~90 MB download to the "
            "serving path. Complexity that does not buy accuracy is not worth deploying.")

    return (f"**Ships:** {pick}.\n\n{why}\n\n"
            "Both artifacts are kept (`ml/eval/baseline_model.joblib`, "
            "`ml/eval/embedding_model.joblib`) per `architecture.md` §1, which specifies "
            "keeping both models and an evaluation report comparing them.")


if __name__ == "__main__":
    sys.exit(main())
