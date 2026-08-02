/**
 * The ML half of the risk decision: TF-IDF + Logistic Regression.
 *
 * Ported from apps/backend/ai/classifier/classifier.py. The Python version
 * unpickled a scikit-learn pipeline; this one evaluates the same fitted
 * parameters, exported to model.json by ml/export_model_json.py. Both were
 * verified to produce identical predicted classes and probabilities (to 1e-9)
 * over the whole dataset — see tools/compare_classifiers.mjs.
 *
 * FEATURES ARE DELIBERATELY RESTRICTED to what the backend actually knows at
 * inference time: the free-text task description and the category. Not
 * `tools_available` (never collected), and no longer `user_skill` — that was
 * dropped on 2026-08-02 after the seed data was rebalanced, at which point it
 * became the weakest coefficient block and the prediction was identical across
 * all three values. Skill-based escalation was always the rule engine's job and
 * stays there: `fixed_wiring_work` carries floor 3 for everyone.
 *
 * FAILURE IS LOUD, NEVER "SAFE"
 * -----------------------------
 * If the model data is missing, malformed, or produces an out-of-range value,
 * `classify()` THROWS. It must never return a low risk level to paper over a
 * broken model — the caller catches it, writes an aiLogs row, and marks the
 * assessment `failed` (CLAUDE.md: "AI pipeline failures must set
 * assessment_status = failed and block the DIY recommendation — never silently
 * fall back to a 'safe' result").
 *
 * Out-of-range predictions are deliberately NOT clamped. Clamping would hide
 * exactly the corruption this check exists to surface.
 *
 * This is only half the decision. `finalRisk = max(ML, rules)`, and the
 * deterministic rule engine in ../ruleEngine/ is what actually guarantees
 * safety-critical escalation — this model's high-risk recall is around 0.65,
 * nowhere near prd.md §7's target.
 */

import modelData from "./model.json";
import { transform, type VectorizerSpec } from "./tfidf";

export const MIN_RISK_LEVEL = 1;
export const MAX_RISK_LEVEL = 5;

/**
 * Raised when the trained model cannot be loaded or used.
 *
 * Deliberately fatal to the assessment. Callers must fail the assessment rather
 * than substitute a default risk level.
 */
export class ModelUnavailableError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ModelUnavailableError";
  }
}

interface ModelBundle {
  blockOrder: string[];
  word: VectorizerSpec;
  char: VectorizerSpec;
  category: { categories: string[][]; handleUnknown: string };
  classifier: {
    coef: number[][];
    intercept: number[];
    classes: number[];
    nFeatures: number;
  };
}

const model = modelData as unknown as ModelBundle;

export interface Classification {
  riskLevel: number;
  confidence: number;
  /** Per-class probabilities, aligned with the model's `classes` order. */
  probabilities: number[];
}

/**
 * Assemble the full feature vector, in the column order the model was fit with.
 *
 * ColumnTransformer concatenated [word | char | category], and the coefficient
 * matrix is indexed against that layout, so the offsets here are not arbitrary —
 * getting them wrong would silently misalign every weight. `blockOrder` is
 * asserted rather than assumed.
 */
function buildFeatures(description: string, category: string): Map<number, number> {
  const expected = ["text", "char", "cat"];
  if (
    model.blockOrder.length !== expected.length ||
    !model.blockOrder.every((b, i) => b === expected[i])
  ) {
    throw new ModelUnavailableError(
      `model.json blockOrder is ${JSON.stringify(model.blockOrder)}, expected ` +
        `${JSON.stringify(expected)} — the exported column layout no longer ` +
        `matches this code.`,
    );
  }

  const features = new Map<number, number>();

  // Block 1: word n-grams.
  const wordVec = transform(model.word, description);
  for (const [col, val] of wordVec) features.set(col, val);

  // Block 2: char_wb n-grams, offset past the word vocabulary.
  const charOffset = Object.keys(model.word.vocabulary).length;
  const charVec = transform(model.char, description);
  for (const [col, val] of charVec) features.set(charOffset + col, val);

  // Block 3: one-hot category, offset past both vocabularies. An unseen category
  // yields all zeros, matching OneHotEncoder(handle_unknown="ignore").
  const catOffset = charOffset + Object.keys(model.char.vocabulary).length;
  const categories = model.category.categories[0] ?? [];
  const idx = categories.indexOf((category ?? "").toLowerCase());
  if (idx >= 0) features.set(catOffset + idx, 1);

  return features;
}

/** Numerically stable softmax. */
function softmax(logits: number[]): number[] {
  const max = Math.max(...logits);
  const exps = logits.map((z) => Math.exp(z - max));
  const sum = exps.reduce((a, b) => a + b, 0);
  return exps.map((e) => e / sum);
}

/**
 * Predict a risk level (1-5) and the model's confidence in it.
 *
 * @throws ModelUnavailableError if the model data is unusable or the prediction
 *         falls outside the valid risk range.
 */
export function classify(description: string, category: string): Classification {
  const { coef, intercept, classes, nFeatures } = model.classifier;

  if (!coef?.length || !intercept?.length || !classes?.length) {
    throw new ModelUnavailableError(
      "model.json is missing classifier parameters (coef/intercept/classes). " +
        "Re-run `python ml/export_model_json.py`.",
    );
  }

  const features = buildFeatures(description, category);

  // Guard the layout: a feature index past the coefficient matrix means the
  // exported model and this code have drifted apart, which would otherwise show
  // up as a quietly wrong probability rather than an error.
  for (const col of features.keys()) {
    if (col >= nFeatures) {
      throw new ModelUnavailableError(
        `feature index ${col} exceeds the model's ${nFeatures} features — ` +
          `model.json and the vectorizer are out of sync.`,
      );
    }
  }

  // logits = X · coefᵀ + intercept, iterating only the non-zero features.
  const logits = coef.map((row, k) => {
    let z = intercept[k];
    for (const [col, val] of features) z += val * row[col];
    return z;
  });

  // Binary logistic regression stores a single coefficient row; multinomial
  // stores one per class. sklearn's predict_proba differs accordingly, so both
  // are handled rather than assuming the multiclass shape.
  const probabilities =
    coef.length === 1
      ? (() => {
          const p = 1 / (1 + Math.exp(-logits[0]));
          return [1 - p, p];
        })()
      : softmax(logits);

  let best = 0;
  for (let i = 1; i < probabilities.length; i++) {
    if (probabilities[i] > probabilities[best]) best = i;
  }

  const riskLevel = classes[best];

  // NOT clamped on purpose. A model returning a level outside 1-5 is corrupt,
  // and clamping would hide it behind a plausible-looking answer.
  if (
    !Number.isFinite(riskLevel) ||
    riskLevel < MIN_RISK_LEVEL ||
    riskLevel > MAX_RISK_LEVEL
  ) {
    throw new ModelUnavailableError(
      `classifier produced out-of-range risk level ${riskLevel}; refusing to ` +
        `substitute a default.`,
    );
  }

  return {
    riskLevel,
    confidence: probabilities[best],
    probabilities,
  };
}
