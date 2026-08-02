/**
 * Port equivalence gate: TypeScript classifier vs the scikit-learn one.
 *
 * Reads `classifier_python_results.json` (written by
 * tools/dump_python_classifier_results.py), replays every row through the
 * TypeScript port, and fails loudly on any disagreement.
 *
 * This is the check that licenses keeping `final_risk = max(ML, rules)` after
 * the Python runtime is gone. A reimplemented TF-IDF is unusually easy to get
 * subtly wrong — sklearn's char_wb analyzer pads each word and has a specific
 * rule for words shorter than n — and every such mistake shifts probabilities
 * silently rather than throwing. Nothing about the app would look broken; the
 * model would just quietly be a bit worse forever.
 *
 * Comparing full probability VECTORS, not just the argmax, is deliberate: an
 * off-by-one window still picks the same winner most of the time, so class-only
 * agreement would hide it.
 *
 * USAGE (from apps/frontend, where tsx is installed)
 *   npx tsx ../../tools/compare_classifiers.mjs
 *
 * Exits non-zero on any mismatch, so it can gate CI.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

const { classify } = await import(
  pathToFileURL(join(ROOT, "apps/frontend/convex/ai/classifier/classify.ts")).href
);

const expected = JSON.parse(
  readFileSync(join(__dirname, "classifier_python_results.json"), "utf-8"),
);

/**
 * Probability tolerance. Both sides do the same arithmetic in IEEE-754 double
 * precision but not in the same ORDER — sklearn accumulates a sparse dot product
 * via BLAS, we accumulate it in a JS loop — so the last couple of bits can
 * differ. 1e-9 is far tighter than any real implementation difference (which
 * would show up in the 1e-3 range or worse) while tolerating that reordering.
 */
const TOLERANCE = 1e-9;

let maxProbDelta = 0;
let classMismatches = 0;
const failures = [];

for (const row of expected.rows) {
  let got;
  try {
    got = classify(row.task_text, row.category);
  } catch (err) {
    failures.push({
      task: row.task_text,
      category: row.category,
      reason: `threw: ${err.message}`,
    });
    continue;
  }

  if (got.riskLevel !== row.predicted) {
    classMismatches += 1;
    failures.push({
      task: row.task_text,
      category: row.category,
      reason: `class python=${row.predicted} typescript=${got.riskLevel}`,
    });
    continue;
  }

  for (let i = 0; i < row.probabilities.length; i++) {
    const delta = Math.abs(row.probabilities[i] - got.probabilities[i]);
    if (delta > maxProbDelta) maxProbDelta = delta;
    if (delta > TOLERANCE) {
      failures.push({
        task: row.task_text,
        category: row.category,
        reason:
          `probability[class ${expected.classes[i]}] differs by ${delta.toExponential(3)} ` +
          `(python=${row.probabilities[i]}, typescript=${got.probabilities[i]})`,
      });
      break;
    }
  }
}

console.log(`compared ${expected.rows.length} rows`);
console.log(`  classes: ${JSON.stringify(expected.classes)}`);
console.log(`  max probability delta: ${maxProbDelta.toExponential(3)} (tolerance ${TOLERANCE})`);
console.log(`  predicted-class mismatches: ${classMismatches}`);

if (failures.length === 0) {
  console.log("\n✅ PASS — the TypeScript classifier matches scikit-learn exactly.");
  process.exit(0);
}

console.error(`\n❌ FAIL — ${failures.length} row(s) disagree.\n`);
for (const f of failures.slice(0, 20)) {
  console.error(`  "${f.task}" (${f.category})`);
  console.error(`      ${f.reason}`);
}
if (failures.length > 20) console.error(`\n  ... and ${failures.length - 20} more.`);
process.exit(1);
