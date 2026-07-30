# Phase 4 — Baseline vs Embedding Model

Reproduce: `python ml/train_baseline.py && python ml/train_embedding_model.py`.

| | Baseline (Phase 3) | Embedding (Phase 4) |
|---|---|---|
| representation | TF-IDF word + char n-grams | `all-MiniLM-L6-v2` sentence embeddings (384-d, frozen) |
| head | Logistic Regression, `class_weight=balanced` | Logistic Regression, `class_weight=balanced` |
| inputs | `task_text`, `category`, `user_skill`, `tools_available` | identical |

Both models are scored by the same code (`ml/evaluation.py`) on the same splits,
so the comparison isolates the representation.

## Held-out test split

Hand-written rows are the trustworthy view — generated rows are paraphrases and
partly measure the generator.

**All test rows (n=81)**

| metric | baseline | embedding | change |
|---|---|---|---|
| accuracy | 0.617 | 0.593 | ▼ -0.025 |
| macro F1 | 0.613 | 0.585 | ▼ -0.028 |
| high-risk recall (≥4 as ≥4) | 0.514 | 0.400 | ▼ -0.114 |
| under-prediction rate | 0.284 | 0.296 | ▲ +0.012 |

**Hand-written test rows only (n=40)**

| metric | baseline | embedding | change |
|---|---|---|---|
| accuracy | 0.650 | 0.600 | ▼ -0.050 |
| macro F1 | 0.646 | 0.592 | ▼ -0.054 |
| high-risk recall (≥4 as ≥4) | 0.529 | 0.412 | ▼ -0.118 |
| under-prediction rate | 0.275 | 0.275 | = +0.000 |

⚠️ **Do not decide from this table alone.** With n=40 the 95% CI on high-risk
recall spans roughly ±0.2, which is wider than any plausible difference between
the two models. It is reported for completeness; the decision rests on the
paired CV below.

## Paired grouped 5-fold cross-validation — the basis for the decision

Both models trained and scored on **identical folds** over all 555 rows, grouped
so a seed and its variants never straddle a fold.

| fold | base macro-F1 | emb macro-F1 | Δ | base HR recall | emb HR recall | Δ |
|---|---|---|---|---|---|---|
| 1 | 0.677 | 0.610 | -0.067 | 0.825 | 0.750 | -0.075 |
| 2 | 0.726 | 0.587 | -0.139 | 0.659 | 0.683 | +0.024 |
| 3 | 0.724 | 0.682 | -0.042 | 0.732 | 0.659 | -0.073 |
| 4 | 0.638 | 0.579 | -0.059 | 0.561 | 0.683 | +0.122 |
| 5 | 0.630 | 0.560 | -0.070 | 0.756 | 0.659 | -0.098 |

| | baseline | embedding | mean Δ | folds embedding wins |
|---|---|---|---|---|
| macro F1 | 0.679 ± 0.041 | 0.604 ± 0.042 | **-0.075** ± 0.033 | 0/5 |
| high-risk recall | 0.706 ± 0.090 | 0.687 ± 0.034 | **-0.020** ± 0.082 | 2/5 |

## Decision — which model ships

**Ships:** the **baseline (TF-IDF + Logistic Regression)**.

high-risk recall is statistically indistinguishable (-0.020, inside the ±0.082 fold spread, embedding winning only 2/5 folds), but the embedding model is decisively **worse** on macro F1: -0.075 ± 0.033, losing 5/5 folds. That margin is more than twice the fold-to-fold spread, so it is a real effect rather than noise.

Why the general-purpose encoder loses here is worth stating, because the result is the opposite of the usual expectation. Risk in this corpus is carried by specific, low-frequency domain tokens — *gas*, *asbestos*, *load-bearing*, *consumer unit*, *breaker*, *fragile*. TF-IDF weights exactly those rare, discriminative terms, and character n-grams catch their morphology (*wiring*/*rewire*). MiniLM instead compresses each sentence into 384 dimensions tuned for general semantic similarity, where *"replace a light fixture"* and *"replace a consumer unit"* sit close together despite being three risk levels apart. With only ~390 training rows there is also far too little signal to learn a head that recovers those distinctions from a general-purpose embedding space. Domain-specific keywords beating general semantics is a well-known outcome on small, jargon-dense corpora.

The cost argument reinforces the same choice: the embedding model would add torch and a ~90 MB download to the serving path for a measurable *loss* in accuracy.

Both artifacts are kept (`ml/eval/baseline_model.joblib`, `ml/eval/embedding_model.joblib`) per `architecture.md` §1, which specifies keeping both models and an evaluation report comparing them.

## Per-class detail — embedding model, test (all rows)

| risk level | precision | recall | F1 | support |
|---|---|---|---|---|
| 1 — safe_diy | 0.62 | 1.00 | 0.77 | 20 |
| 2 — diy_with_supervision | 0.47 | 0.57 | 0.52 | 14 |
| 3 — professional_recommended | 0.46 | 0.50 | 0.48 | 12 |
| 4 — professional_required | 1.00 | 0.83 | 0.91 | 12 |
| 5 — dangerous | 0.44 | 0.17 | 0.25 | 23 |

### Confusion matrix

| true \ pred | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| **1** | 20 | 0 | 0 | 0 | 0 |
| **2** | 0 | 8 | 4 | 0 | 2 |
| **3** | 0 | 3 | 6 | 0 | 3 |
| **4** | 0 | 2 | 0 | 10 | 0 |
| **5** | 12 | 4 | 3 | 0 | 4 |

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
