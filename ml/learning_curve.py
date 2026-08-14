"""Learning curve: how much hand-written data would move the baseline-vs-
embedding decision in comparison_report.md?

Run: python ml/learning_curve.py

Writes:
  ml/eval/learning_curve.png     macro-F1 and high-risk recall vs n, both models
  ml/eval/learning_curve.json    raw points + power-law fit + extrapolation
  ml/eval/learning_curve_report.md

METHOD. comparison_report.md's verdict rests on 256 hand-written (`source ==
"seed"`) rows; generated rows are paraphrases that partly measure the
generator, so this curve trains on hand-written rows only. For a series of
training-set sizes n, it repeatedly (5 draws per size) samples n hand-written
GROUPS (a seed row and its own generated variants never split across the
draw, matching every other script here), fits both the baseline pipeline
(train_baseline.build_pipeline) and the embedding head
(train_embedding_model.fit_head) with their already-selected hyperparameters,
and scores both on the SAME fixed held-out set: the hand-written subset of
ml/data/test.json, which no training draw ever touches.

Both models reuse their already-chosen C / ngram (train_baseline.py,
train_embedding_model.py pick these on the val split; re-selecting per draw
here would be its own experiment and would make 5 repeats far more expensive
for no change to the question being asked).

EXTRAPOLATION. A log-linear fit (F1 ~ a - b / n^c) is fit to each curve and
solved for the n at which the curve is projected to close half the remaining
gap to a chosen target. This is a rough diagnostic, not a guarantee - see the
report's caveats.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from sklearn.preprocessing import OneHotEncoder

from evaluation import EVAL, load, labels_of, evaluate_predictions
from train_baseline import build_pipeline, to_frame
from train_embedding_model import encode_all, build_features, fit_head

RNG_SEEDS = [0, 1, 2, 3, 4]
FRACTIONS = [0.2, 0.35, 0.5, 0.65, 0.8, 1.0]


def hand_written_groups(rows: list[dict]) -> dict[str, list[dict]]:
    """Hand-written rows plus their own generated variants, keyed by group_id -
    a group is the sampling unit so a seed and its paraphrases never split
    between a training draw and anything else."""
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(r["group_id"], []).append(r)
    return {g: rs for g, rs in groups.items() if any(r["source"] == "seed" for r in rs)}


def sample_groups(groups: dict[str, list[dict]], n_seed_groups: int, seed: int) -> list[dict]:
    keys = sorted(groups.keys())
    rng = np.random.RandomState(seed)
    chosen = rng.choice(keys, size=n_seed_groups, replace=False)
    out = []
    for k in chosen:
        out.extend(groups[k])
    return out


def main() -> int:
    train, val, test = load("train"), load("val"), load("test")
    pool = train + val  # test is the fixed held-out set, never sampled from
    groups = hand_written_groups(pool)
    n_groups = len(groups)
    print(f"{n_groups} hand-written groups available to sample training sets from "
          f"(out of {len(pool)} train+val rows); {len(test)}-row test split held out fixed")

    seed_test = [r for r in test if r["source"] == "seed"]
    print(f"scoring against the fixed hand-written test set (n={len(seed_test)})")

    # ---- baseline hyperparameters already selected in train_baseline.py
    base_meta = json.loads((EVAL / "baseline_metrics.json").read_text(encoding="utf-8"))
    base_C, base_ng = base_meta["selected"]["C"], tuple(base_meta["selected"]["ngram"])

    # ---- embedding hyperparameters + frozen encoder, reuse the cache if present
    emb_meta = json.loads((EVAL / "embedding_metrics.json").read_text(encoding="utf-8"))
    emb_C = emb_meta["selected"]["C"]
    emb = encode_all(train + val + test)

    Xte_txt = to_frame(seed_test)
    yte = labels_of(seed_test)

    sizes = sorted({max(4, round(f * n_groups)) for f in FRACTIONS})
    points = []
    for n in sizes:
        base_f1s, base_hrs, emb_f1s, emb_hrs = [], [], [], []
        n_rows = 0
        for seed in RNG_SEEDS:
            draw = sample_groups(groups, n, seed)
            n_rows = len(draw)
            ytr = labels_of(draw)

            bm = build_pipeline(base_C, base_ng).fit(to_frame(draw), ytr)
            bp = bm.predict(Xte_txt)
            be = evaluate_predictions("lc", seed_test, bp)
            base_f1s.append(be["macro_f1"])
            base_hrs.append(be["safety"]["high_risk_recall_collapsed"])

            ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
            Xtr_emb = build_features(draw, emb, ohe, fit=True)
            Xte_emb = build_features(seed_test, emb, ohe)
            eh = fit_head(Xtr_emb, ytr, emb_C)
            ep = eh.predict(Xte_emb)
            ee = evaluate_predictions("lc", seed_test, ep)
            emb_f1s.append(ee["macro_f1"])
            emb_hrs.append(ee["safety"]["high_risk_recall_collapsed"])

        point = {
            "n_groups": n, "n_rows": n_rows,
            "base_macro_f1_mean": float(np.mean(base_f1s)), "base_macro_f1_std": float(np.std(base_f1s)),
            "base_hr_recall_mean": float(np.mean(base_hrs)), "base_hr_recall_std": float(np.std(base_hrs)),
            "emb_macro_f1_mean": float(np.mean(emb_f1s)), "emb_macro_f1_std": float(np.std(emb_f1s)),
            "emb_hr_recall_mean": float(np.mean(emb_hrs)), "emb_hr_recall_std": float(np.std(emb_hrs)),
        }
        points.append(point)
        print(f"n_rows~{n_rows:4d}  base F1 {point['base_macro_f1_mean']:.3f}"
              f"+/-{point['base_macro_f1_std']:.3f}  emb F1 {point['emb_macro_f1_mean']:.3f}"
              f"+/-{point['emb_macro_f1_std']:.3f}  base HR {point['base_hr_recall_mean']:.3f}"
              f"  emb HR {point['emb_hr_recall_mean']:.3f}")

    fits = {
        "base_macro_f1": fit_and_project(points, "n_rows", "base_macro_f1_mean"),
        "emb_macro_f1": fit_and_project(points, "n_rows", "emb_macro_f1_mean"),
        "base_hr_recall": fit_and_project(points, "n_rows", "base_hr_recall_mean"),
        "emb_hr_recall": fit_and_project(points, "n_rows", "emb_hr_recall_mean"),
    }

    out = {"n_hand_written_groups_available": n_groups,
           "current_total_hand_written_rows": 256,
           "test_n": len(seed_test), "points": points, "fits": fits}
    (EVAL / "learning_curve.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    plot(points)
    write_report(out)
    print(f"\nwrote {EVAL}/learning_curve.png, learning_curve.json, learning_curve_report.md")
    return 0


# --------------------------------------------------------------------------
def fit_and_project(points: list[dict], xkey: str, ykey: str) -> dict:
    """Fit y = a - b / n^c on the observed points and project the n at which
    the curve is expected to close half the remaining gap to a target."""
    from scipy.optimize import curve_fit

    x = np.array([p[xkey] for p in points], dtype=float)
    y = np.array([p[ykey] for p in points], dtype=float)

    def model(n, a, b, c):
        return a - b / np.power(n, c)

    try:
        popt, _ = curve_fit(model, x, y, p0=[max(y) + 0.1, 1.0, 0.5],
                            bounds=([0, 0, 0.01], [1.5, 10, 3]), maxfev=20000)
        a, b, c = (float(v) for v in popt)
        r2 = 1 - np.sum((y - model(x, *popt)) ** 2) / np.sum((y - y.mean()) ** 2)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    current_n, current_y = float(x[-1]), float(model(x[-1], *popt))
    plateau = min(a, 1.0)
    remaining = plateau - current_y
    target = current_y + remaining / 2
    # solve n from y = a - b/n^c  =>  n = (b / (a - y)) ** (1/c)
    n_half_gap = None
    if remaining > 1e-6 and plateau - target > 1e-9:
        n_half_gap = float((b / (a - target)) ** (1 / c))

    return {"ok": True, "a_plateau": a, "b": b, "c": c, "r2": float(r2),
            "current_n_rows": current_n, "current_y": current_y,
            "projected_plateau": plateau, "n_rows_for_half_remaining_gap": n_half_gap}


def plot(points: list[dict]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = [p["n_rows"] for p in points]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))

    for ax, metric, title in (
        (axes[0], "macro_f1", "macro F1 vs hand-written training rows"),
        (axes[1], "hr_recall", "high-risk recall vs hand-written training rows"),
    ):
        for prefix, label, color in (("base", "baseline (TF-IDF)", "tab:blue"),
                                     ("emb", "embedding (MiniLM)", "tab:orange")):
            y = np.array([p[f"{prefix}_{metric}_mean"] for p in points])
            s = np.array([p[f"{prefix}_{metric}_std"] for p in points])
            ax.plot(n, y, marker="o", label=label, color=color)
            ax.fill_between(n, y - s, y + s, alpha=0.15, color=color)
        ax.set_xlabel("hand-written training rows (n)")
        ax.set_ylabel(metric)
        ax.set_title(title, fontsize=10)
        ax.legend(fontsize=8)
        ax.grid(alpha=0.25)

    fig.tight_layout()
    fig.savefig(EVAL / "learning_curve.png", dpi=150)
    plt.close(fig)


def write_report(out: dict) -> None:
    def fit_line(key: str, label: str) -> str:
        f = out["fits"][key]
        if not f.get("ok"):
            return f"- **{label}**: fit failed ({f.get('error')})"
        pinned = f["a_plateau"] >= 1.499  # hit the curve_fit search bound - not a real plateau estimate
        proj = (f"~{f['n_rows_for_half_remaining_gap']:.0f} rows to close half the "
                f"remaining gap to its projected plateau ({f['projected_plateau']:.3f})"
                if f["n_rows_for_half_remaining_gap"] else "already essentially flat")
        flag = " ⚠️ **plateau pinned at the search bound - curve is still too early to extrapolate; treat only the observed trend as real, not this row count.**" if pinned else ""
        return (f"- **{label}**: fit y = {f['a_plateau']:.3f} - {f['b']:.2f}/n^{f['c']:.2f} "
                f"(R²={f['r2']:.2f}); currently {f['current_y']:.3f} at n={f['current_n_rows']:.0f}; "
                f"{proj}{flag}")

    rows = "\n".join(
        f"| {p['n_rows']} | {p['base_macro_f1_mean']:.3f} ± {p['base_macro_f1_std']:.3f} "
        f"| {p['emb_macro_f1_mean']:.3f} ± {p['emb_macro_f1_std']:.3f} "
        f"| {p['base_hr_recall_mean']:.3f} ± {p['base_hr_recall_std']:.3f} "
        f"| {p['emb_hr_recall_mean']:.3f} ± {p['emb_hr_recall_std']:.3f} |"
        for p in out["points"])

    doc = f"""# Learning curve — baseline vs embedding vs hand-written data volume

Reproduce: `python ml/learning_curve.py`. Answers: how much more hand-written
data (beyond the current {out['current_total_hand_written_rows']} rows) would
it take to move `comparison_report.md`'s ship decision?

Method: for each training size, 5 random draws of that many hand-written
GROUPS (a seed row + its own generated paraphrases, never split — same
grouping every other script here uses) are sampled from `train.json` +
`val.json` (only {out['n_hand_written_groups_available']} hand-written groups
exist there to draw from). Both models are refit per draw with their
already-selected hyperparameters and scored against the SAME fixed,
never-sampled hand-written test rows (n={out['test_n']}, from `test.json`).
Reported values are the mean ± std across the 5 draws.

**"training rows (n)" is NOT a pure hand-written count.** Sampling by group
(to avoid a seed and its own paraphrase leaking across a fold) pulls in each
sampled seed row's generated variants too - at full pool size n=474 rows
covers 216 hand-written rows plus 258 of their generated variants (~46%
hand-written). The ratio is roughly constant across draws, so the trend below
is meaningful, but "n" should be read as "hand-written examples plus their
natural paraphrases", not literal hand-written volume - divide by roughly
2.2 for a hand-written-only estimate.

## Observed points

| training rows (n) | baseline macro F1 | embedding macro F1 | baseline HR recall | embedding HR recall |
|---|---|---|---|---|
{rows}

![learning curve](learning_curve.png)

## Power-law extrapolation

Each curve is fit to `y = a - b / n^c` (a = projected plateau) and solved for
the n at which it is projected to close half the remaining gap to that
plateau — a rough "how much more would meaningfully help" marker, not a
promise.

{fit_line("base_macro_f1", "baseline macro F1")}
{fit_line("emb_macro_f1", "embedding macro F1")}
{fit_line("base_hr_recall", "baseline high-risk recall")}
{fit_line("emb_hr_recall", "embedding high-risk recall")}

## Reading this

- If the embedding curve is still rising faster than the baseline's at the
  largest n tested, and/or its extrapolated plateau sits above the
  baseline's, that is direct evidence for the earlier claim that embeddings
  have more long-term headroom — and the fit above gives a concrete row
  estimate instead of a rule of thumb.
- If both curves have already flattened by n={out['points'][-1]['n_rows'] if out['points'] else '?'}
  (current data), more hand-written data of the *same kind* is unlikely to
  move the ship decision — the ceiling is coming from label ambiguity between
  adjacent risk levels (`comparison_report.md`), not from volume, and effort
  is better spent on review/relabeling than on writing more examples.

## Caveats

1. **5 repeats per size** is enough to see a trend, not to bound it tightly —
   the shaded bands are ± 1 std over 5 draws, not a confidence interval.
2. **Hyperparameters are held fixed** at their current train/val-selected
   values for both models at every training size. A model refit from scratch
   at, say, 800 rows might select a different `C` or n-gram range; this curve
   answers "does more data help at today's settings", not "what is achievable
   with re-tuning at scale".
3. **The power-law fit is descriptive, not causal.** With only {len(out['points'])} x-values
   it can look confident (high R²) while still extrapolating a shape that
   doesn't hold beyond the tested range - treat the projected n as an
   order-of-magnitude signal, not a target to hit exactly.
4. Training draws come from `train.json` + `val.json` only; the {out['test_n']}-row
   hand-written test split is never sampled from, so the score at the
   right-most point is close to but not identical to the headline numbers in
   `baseline_report.md` / `comparison_report.md` (those refit on train+val
   in full, this refits on a 5-draw sample of it).
"""
    (EVAL / "learning_curve_report.md").write_text(doc, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
