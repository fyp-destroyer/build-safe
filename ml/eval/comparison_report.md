# Phase 4 — Baseline vs Embedding Model

Reproduce: `python ml/train_baseline.py && python ml/train_embedding_model.py`.

| | Baseline (Phase 3) | Embedding (Phase 4) |
|---|---|---|
| representation | TF-IDF word + char n-grams | `all-MiniLM-L6-v2` sentence embeddings (384-d, frozen) |
| head | Logistic Regression, `class_weight=balanced` | Logistic Regression, `class_weight=balanced` |
| inputs | `task_text`, `category`, `user_skill` | identical |

Both models are scored by the same code (`ml/evaluation.py`) on the same splits,
so the comparison isolates the representation.

## Held-out test split

Hand-written rows are the trustworthy view — generated rows are paraphrases and
partly measure the generator.

**All test rows (n=81)**

| metric | baseline | embedding | change |
|---|---|---|---|
| accuracy | 0.432 | 0.420 | ▼ -0.012 |
| macro F1 | 0.415 | 0.394 | ▼ -0.021 |
| high-risk recall (≥4 as ≥4) | 0.571 | 0.571 | = +0.000 |
| under-prediction rate | 0.346 | 0.321 | ▼ -0.025 |

**Hand-written test rows only (n=40)**

| metric | baseline | embedding | change |
|---|---|---|---|
| accuracy | 0.425 | 0.400 | ▼ -0.025 |
| macro F1 | 0.411 | 0.371 | ▼ -0.040 |
| high-risk recall (≥4 as ≥4) | 0.529 | 0.588 | ▲ +0.059 |
| under-prediction rate | 0.350 | 0.325 | ▼ -0.025 |

⚠️ **Do not decide from this table alone.** With n=40 the 95% CI on high-risk
recall spans roughly ±0.2, which is wider than any plausible difference between
the two models. It is reported for completeness; the decision rests on the
paired CV below.

## Paired grouped 5-fold cross-validation — the basis for the decision

Both models trained and scored on **identical folds** over all 555 rows, grouped
so a seed and its variants never straddle a fold.

| fold | base macro-F1 | emb macro-F1 | Δ | base HR recall | emb HR recall | Δ |
|---|---|---|---|---|---|---|
| 1 | 0.288 | 0.315 | +0.027 | 0.650 | 0.650 | +0.000 |
| 2 | 0.420 | 0.363 | -0.057 | 0.561 | 0.634 | +0.073 |
| 3 | 0.456 | 0.400 | -0.056 | 0.732 | 0.659 | -0.073 |
| 4 | 0.316 | 0.326 | +0.010 | 0.659 | 0.488 | -0.171 |
| 5 | 0.262 | 0.288 | +0.026 | 0.634 | 0.512 | -0.122 |

| | baseline | embedding | mean Δ | folds embedding wins |
|---|---|---|---|---|
| macro F1 | 0.349 ± 0.076 | 0.338 ± 0.039 | **-0.010** ± 0.039 | 3/5 |
| high-risk recall | 0.647 ± 0.055 | 0.589 ± 0.073 | **-0.059** ± 0.087 | 1/5 |

## Decision — which model ships

**Ships:** the **baseline (TF-IDF + Logistic Regression)**.

neither difference clears the fold-to-fold noise — macro F1 -0.010 (±0.039), high-risk recall -0.059 (±0.087). With no measurable gain, the tie is broken on cost: the baseline is a few hundred KB of scikit-learn with no extra runtime dependency, while the embedding model adds torch and a ~90 MB download to the serving path. Complexity that does not buy accuracy is not worth deploying.

Both artifacts are kept (`ml/eval/baseline_model.joblib`, `ml/eval/embedding_model.joblib`) per `architecture.md` §1, which specifies keeping both models and an evaluation report comparing them.

## Per-class detail — embedding model, test (all rows)

| risk level | precision | recall | F1 | support |
|---|---|---|---|---|
| 1 — safe_diy | 0.61 | 0.70 | 0.65 | 20 |
| 2 — diy_with_supervision | 0.21 | 0.29 | 0.24 | 14 |
| 3 — professional_recommended | 0.15 | 0.17 | 0.16 | 12 |
| 4 — professional_required | 0.50 | 0.42 | 0.45 | 12 |
| 5 — dangerous | 0.56 | 0.39 | 0.46 | 23 |

### Confusion matrix

| true \ pred | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| **1** | 14 | 2 | 4 | 0 | 0 |
| **2** | 3 | 4 | 5 | 0 | 2 |
| **3** | 4 | 2 | 2 | 3 | 1 |
| **4** | 1 | 2 | 0 | 5 | 4 |
| **5** | 1 | 9 | 2 | 2 | 9 |

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
