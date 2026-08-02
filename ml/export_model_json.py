"""Export the trained scikit-learn classifier to JSON for the TypeScript runtime.

WHY THIS EXISTS
---------------
The shipped model is a TF-IDF + LogisticRegression pipeline, pickled with joblib
and previously loaded in-process by the Python backend. The backend is now Convex
(TypeScript), which cannot unpickle a scikit-learn object.

Dropping the classifier was not an option. `final_risk = max(ML, rules)` is
non-negotiable (CLAUDE.md, rules.md §4.2), and the classifier is not dead weight:
after the `user_skill` confound was fixed and the model retrained without it
(2026-08-02), test-split `max(ML, rules)` high-risk recall rose 0.686 -> 0.743.
Removing a term from a max() can only lower the result, so deleting it would have
been a measurable safety regression.

The way out is that this model is only numbers. TF-IDF is a vocabulary, a set of
IDF weights and a normalisation; logistic regression is a matrix multiply and a
softmax. All of it ports to TypeScript exactly — not approximately — so the
prediction is preserved rather than reimplemented by eye.

WHAT IS EXPORTED
----------------
Everything the TypeScript vectorizer needs to reproduce sklearn's `transform`
byte-for-byte:

  word block  vocabulary, idf, ngram_range, the analyzer settings
  char block  same, for the char_wb analyzer
  category    the one-hot categories, in the column order the model was fit with
  classifier  coef_, intercept_, classes_

Column order matters: ColumnTransformer concatenates [word | char | category],
and the coefficient matrix is indexed against that layout. It is recorded here
explicitly rather than assumed.

USAGE (one-off; re-run whenever the model is retrained)
-------------------------------------------------------
    python ml/export_model_json.py

Writes apps/frontend/convex/ai/classifier/model.json, then verify with:

    cd apps/frontend && npx tsx ../../tools/compare_classifiers.mjs

This script runs at BUILD time on a developer machine, never at request time.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "ml" / "eval" / "baseline_model.joblib"
OUT = ROOT / "apps" / "frontend" / "convex" / "ai" / "classifier" / "model.json"


def export_tfidf(vec) -> dict:
    """Serialize one fitted TfidfVectorizer.

    The vocabulary is emitted as term -> column index, exactly as sklearn holds
    it, so the TypeScript side never has to guess an ordering.
    """
    return {
        "vocabulary": {term: int(idx) for term, idx in vec.vocabulary_.items()},
        "idf": [float(x) for x in vec.idf_],
        "analyzer": vec.analyzer,
        "ngramRange": list(vec.ngram_range),
        "lowercase": bool(vec.lowercase),
        "sublinearTf": bool(vec.sublinear_tf),
        "stripAccents": vec.strip_accents,
        "tokenPattern": vec.token_pattern,
        "norm": vec.norm,
    }


def main() -> int:
    if not MODEL_PATH.exists():
        raise SystemExit(f"model artifact not found: {MODEL_PATH}")

    bundle = joblib.load(MODEL_PATH)
    pipeline = bundle["model"]

    column_transformer = pipeline.named_steps["features"]
    clf = pipeline.named_steps["clf"]

    blocks = dict(
        (name, transformer)
        for name, transformer, _cols in column_transformer.transformers_
    )

    word = blocks["text"]
    char = blocks["char"]
    cat = blocks["cat"]

    # The order ColumnTransformer concatenates blocks in. The coefficient matrix
    # is indexed against this layout, so it is recorded rather than assumed.
    order = [name for name, _t, _c in column_transformer.transformers_]
    if order != ["text", "char", "cat"]:
        raise SystemExit(f"unexpected ColumnTransformer order {order}; export needs updating")

    n_word = len(word.vocabulary_)
    n_char = len(char.vocabulary_)
    n_cat = sum(len(c) for c in cat.categories_)

    coef = np.asarray(clf.coef_, dtype=float)
    intercept = np.asarray(clf.intercept_, dtype=float)

    expected = n_word + n_char + n_cat
    if coef.shape[1] != expected:
        raise SystemExit(
            f"feature count mismatch: coef_ has {coef.shape[1]} columns but the "
            f"transformers produce {expected} ({n_word} word + {n_char} char + {n_cat} cat)"
        )

    payload = {
        "_comment": (
            "GENERATED FILE - do not edit. Source: ml/eval/baseline_model.joblib "
            "via ml/export_model_json.py. Verify any change with "
            "tools/compare_classifiers.mjs."
        ),
        "blockOrder": order,
        "word": export_tfidf(word),
        "char": export_tfidf(char),
        "category": {
            # One list per input column; the model was fit on a single column
            # (["category"]), so this has one entry.
            "categories": [[str(v) for v in cats] for cats in cat.categories_],
            "handleUnknown": cat.handle_unknown,
        },
        "classifier": {
            "coef": [[float(x) for x in row] for row in coef],
            "intercept": [float(x) for x in intercept],
            "classes": [int(c) for c in clf.classes_],
            "nFeatures": int(coef.shape[1]),
        },
        "meta": {
            "C": float(bundle.get("C", 0)),
            "ngram": list(bundle.get("ngram", [])),
            "features": list(bundle.get("features", [])),
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload), encoding="utf-8")

    size_kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT}  ({size_kb:.0f} KB)")
    print(f"  word vocab : {n_word}")
    print(f"  char vocab : {n_char}")
    print(f"  category   : {n_cat} ({cat.categories_[0].tolist()})")
    print(f"  classes    : {payload['classifier']['classes']}")
    print(f"  features   : {expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
