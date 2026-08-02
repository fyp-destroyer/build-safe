/**
 * A faithful TypeScript reimplementation of scikit-learn's TfidfVectorizer
 * transform path, for the two vectorizers the shipped model was fit with.
 *
 * This is NOT a general-purpose TF-IDF. It reproduces one specific
 * configuration, and every departure from sklearn's exact behaviour would be a
 * silent accuracy change rather than an error — which is why
 * tools/compare_classifiers.mjs asserts identical probabilities against the
 * Python original for every row of the dataset.
 *
 * The configuration being reproduced (from ml/train_baseline.py):
 *
 *   word block  TfidfVectorizer(ngram_range=(1,2), sublinear_tf=True, min_df=1,
 *                               strip_accents="unicode")
 *   char block  TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5),
 *                               sublinear_tf=True, min_df=2)
 *
 * plus sklearn's defaults: lowercase=True, token_pattern=r"(?u)\b\w\w+\b",
 * norm="l2", use_idf=True, smooth_idf=True.
 *
 * Vocabulary and IDF weights are not recomputed here — they are loaded from
 * model.json exactly as they were fitted, so `min_df` and the document
 * statistics never need to be re-derived.
 */

export interface VectorizerSpec {
  vocabulary: Record<string, number>;
  idf: number[];
  analyzer: string;
  ngramRange: [number, number];
  lowercase: boolean;
  sublinearTf: boolean;
  stripAccents: string | null;
  tokenPattern: string;
  norm: string;
}

/**
 * sklearn's `strip_accents="unicode"`: NFKD-normalise, then drop combining marks.
 *
 * Only applied to the word block — the char block was fitted without it, and
 * applying it there anyway would shift every char n-gram containing an accent.
 */
function stripAccentsUnicode(s: string): string {
  return s.normalize("NFKD").replace(/\p{Mn}/gu, "");
}

/**
 * sklearn's `_white_spaces = re.compile(r"\s\s+")` collapse, applied by the
 * char_wb analyzer before windowing. Runs of whitespace become a single space;
 * a lone space is left as-is.
 */
function collapseWhitespace(s: string): string {
  return s.replace(/\s\s+/g, " ");
}

/**
 * sklearn's default token pattern, r"(?u)\b\w\w+\b" — tokens of two or more
 * word characters.
 *
 * `\w` in Python's `re` with the UNICODE flag matches letters, digits and
 * underscore across scripts. JavaScript's `\w` is ASCII-only, so the Unicode
 * property escapes are spelled out to keep the two in step for non-ASCII input.
 */
const TOKEN_RE = /[\p{L}\p{N}_]{2,}/gu;

function tokenize(text: string): string[] {
  return text.match(TOKEN_RE) ?? [];
}

/**
 * sklearn's `_word_ngrams`: unigrams (when min_n == 1) plus joined n-grams up
 * to max_n, space-separated, in sklearn's exact emission order.
 */
function wordNgrams(tokens: string[], minN: number, maxN: number): string[] {
  const out: string[] = [];
  let start = minN;

  if (maxN !== 1) {
    if (minN === 1) {
      out.push(...tokens);
      start = 2;
    }
    const n0 = tokens.length;
    for (let n = start; n < Math.min(maxN + 1, n0 + 1); n++) {
      for (let i = 0; i <= n0 - n; i++) {
        out.push(tokens.slice(i, i + n).join(" "));
      }
    }
    return out;
  }

  return [...tokens];
}

/**
 * sklearn's `_char_wb_ngrams`.
 *
 * Each whitespace-separated word is padded with one space on each side, then
 * n-grams slide within that padded word — so n-grams never span a word boundary,
 * and the padding makes word-initial and word-final morphology distinguishable.
 *
 * The `if (offset === 0) break;` is not an optimisation: it reproduces
 * sklearn's rule that a word shorter than n contributes its padded form exactly
 * ONCE rather than once per n. Dropping it would double-count short words.
 */
function charWbNgrams(text: string, minN: number, maxN: number): string[] {
  const doc = collapseWhitespace(text);
  const out: string[] = [];

  for (const rawWord of doc.split(" ")) {
    if (rawWord === "") continue;
    const w = ` ${rawWord} `;
    const wLen = w.length;

    for (let n = minN; n <= maxN; n++) {
      let offset = 0;
      out.push(w.slice(offset, offset + n));
      while (offset + n < wLen) {
        offset += 1;
        out.push(w.slice(offset, offset + n));
      }
      if (offset === 0) break;
    }
  }
  return out;
}

/** Every analyzer feature for one document, in sklearn's emission order. */
function analyze(spec: VectorizerSpec, text: string): string[] {
  let doc = text ?? "";
  if (spec.lowercase) doc = doc.toLowerCase();
  if (spec.stripAccents === "unicode") doc = stripAccentsUnicode(doc);

  const [minN, maxN] = spec.ngramRange;
  if (spec.analyzer === "char_wb") return charWbNgrams(doc, minN, maxN);
  if (spec.analyzer === "word") return wordNgrams(tokenize(doc), minN, maxN);
  throw new Error(`tfidf: unsupported analyzer ${JSON.stringify(spec.analyzer)}`);
}

/**
 * Transform one document into a sparse TF-IDF vector, as `column -> value`.
 *
 * Sparse rather than a dense 9,318-wide array because a task description touches
 * only a few hundred columns; the dot product later iterates the non-zeros.
 *
 * Order of operations matches sklearn exactly:
 *   1. count features present in the fitted vocabulary (unknown terms dropped)
 *   2. sublinear_tf: tf = 1 + ln(tf)
 *   3. multiply by the fitted idf
 *   4. L2-normalise
 */
export function transform(spec: VectorizerSpec, text: string): Map<number, number> {
  const counts = new Map<number, number>();

  for (const feature of analyze(spec, text)) {
    const col = spec.vocabulary[feature];
    // Terms absent from the fitted vocabulary are dropped, exactly as sklearn
    // does at transform time — a vocabulary is never extended by inference.
    if (col === undefined) continue;
    counts.set(col, (counts.get(col) ?? 0) + 1);
  }

  const vec = new Map<number, number>();
  for (const [col, count] of counts) {
    const tf = spec.sublinearTf ? 1 + Math.log(count) : count;
    vec.set(col, tf * spec.idf[col]);
  }

  if (spec.norm === "l2") {
    let sumSq = 0;
    for (const v of vec.values()) sumSq += v * v;
    const norm = Math.sqrt(sumSq);
    // sklearn leaves an all-zero row alone rather than dividing by zero — a
    // description with no known terms is legitimately the zero vector.
    if (norm > 0) {
      for (const [col, v] of vec) vec.set(col, v / norm);
    }
  } else if (spec.norm && spec.norm !== "none") {
    throw new Error(`tfidf: unsupported norm ${JSON.stringify(spec.norm)}`);
  }

  return vec;
}
