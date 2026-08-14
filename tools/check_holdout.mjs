/**
 * Held-out validation of the rule engine, on tasks it was never tuned against.
 *
 * `ml/data/holdout_rules.json` contains fresh tasks that appear nowhere in the
 * training data. It was written and committed BEFORE the rules it tests, so a
 * rule cannot have been fitted to it.
 *
 * Half of it is adversarial NEGATIVES — superficially similar tasks that must
 * NOT escalate ("lean a ladder against the wall", "replace a rotten fence
 * post", "swap the faceplate on an existing socket"). Overfitting shows up as
 * an over-broad rule just as much as a narrow one, and positives alone would
 * not catch that: a rule keyed on the bare word "lean" or "rotten" scores
 * perfectly on positives and fails here.
 *
 * Escalate means the rule engine alone reaches risk >= 4. The ML classifier is
 * not consulted — this measures the deterministic layer on its own, since that
 * is what the rules change.
 *
 * PORTED FROM PYTHON 2026-08-12. The original `ml/check_holdout.py` imported
 * `apps/backend/ai/rule_engine`, deleted in the Convex migration, so it had
 * stopped running at all. It also passed a `user_skill` per row; the shipped
 * catalog has no skill-gated rule (every `requiresSkill` is empty, and the old
 * `electrical_work_by_beginner` was replaced by `fixed_wiring_work` at floor 3
 * for everyone), so that field could no longer change an outcome and was
 * dropped from the fixture along with it.
 *
 * USAGE (from apps/frontend, where tsx is installed)
 *   npx tsx ../../tools/check_holdout.mjs
 *
 * Exits non-zero on any failure, so it can gate CI.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const HOLDOUT_PATH = join(ROOT, "ml/data/holdout_rules.json");

// pathToFileURL, not a bare path: on Windows an absolute path starts "C:\",
// which the ESM loader reads as a URL scheme named "c" and rejects.
const { evaluate, requiredFollowups } = await import(
  pathToFileURL(join(ROOT, "apps/frontend/convex/ai/ruleEngine/rules.ts")).href
);

const rows = JSON.parse(readFileSync(HOLDOUT_PATH, "utf-8"));

const byFamily = new Map();
const failures = [];

for (const row of rows) {
  const base = { description: row.task_text, category: row.category };

  // Production never assesses a job with an unanswered required follow-up, so
  // answer them all safely. Any escalation seen here therefore comes from a
  // hazard rule, not from a missing answer — which is what this file tests.
  const fields = requiredFollowups({ ...base, followupAnswers: {} });
  const answers = Object.fromEntries(fields.map((f) => [f, true]));

  const { risk, triggered } = evaluate({ ...base, followupAnswers: answers });
  const want = row.expect === "escalate";
  const ok = risk >= 4 === want;

  if (!byFamily.has(row.family)) byFamily.set(row.family, []);
  byFamily.get(row.family).push(ok);
  if (!ok) failures.push({ row, risk, triggered, want });
}

const line = "=".repeat(74);
console.log(line);
console.log("HELD-OUT RULE VALIDATION");
console.log(`  holdout_rules.json: ${rows.length} fresh tasks, none in the training data`);
console.log(line);

for (const fam of [...byFamily.keys()].sort()) {
  const results = byFamily.get(fam);
  const passed = results.filter(Boolean).length;
  console.log(`  ${fam.padEnd(16)} ${passed}/${results.length} correct`);
}

const pos = rows.filter((r) => r.expect === "escalate").length;
const neg = rows.length - pos;
const posFail = failures.filter((f) => f.want).length;
const negFail = failures.length - posFail;

console.log();
console.log(`  positives caught : ${pos - posFail}/${pos}  (missed hazards — the recall side)`);
console.log(`  negatives held   : ${neg - negFail}/${neg}  (false alarms — the over-broad side)`);

if (failures.length > 0) {
  console.log(`\n  ${failures.length} FAILURE(S):`);
  for (const { row, risk, triggered, want } of failures) {
    console.log(`    [${want ? "MISSED" : "FALSE ALARM"}] risk=${risk} ${JSON.stringify(triggered)}`);
    console.log(`      ${row.task_text.slice(0, 66)}`);
    console.log(`      why it matters: ${row.rationale}`);
  }
  process.exit(1);
}

console.log("\n  All held-out cases behave correctly.");
