/**
 * Rule engine behaviour gate.
 *
 * Replays 579 tasks x 4 follow-up answer states = 2,316 evaluations through the
 * TypeScript rule engine and diffs risk level, the exact triggered-rule list
 * (order included), explanation text, derived follow-ups and next-question
 * against a committed expectation file.
 *
 * Risk level alone would be far too weak a check: two engines can agree on "3"
 * while disagreeing about which hazards produced it, which is the failure that
 * matters.
 *
 * TWO ERAS OF THIS FILE
 * ---------------------
 * It was written to prove the Python -> TypeScript port was faithful, comparing
 * against `rule_engine_python_results.json` — outputs captured from the original
 * FastAPI engine before `apps/backend` was deleted. That comparison passed on
 * all 2,316 evaluations, and that file is still committed as the evidence.
 *
 * On 2026-08-03 the engine's behaviour was deliberately changed (three-valued
 * answers, two dead escalation floors fixed, follow-up questions reworded), so
 * matching Python is no longer the goal — 949 of those evaluations SHOULD now
 * differ. The Python file is therefore frozen history, and this script compares
 * against `rule_engine_expected.json`: a snapshot of current, reviewed
 * behaviour.
 *
 * That keeps the thing worth keeping. The gate no longer proves parity with a
 * deleted implementation, but it still catches the failure that actually
 * threatens users: a change to the catalog or the engine that silently moves a
 * risk level nobody meant to move.
 *
 * USAGE (from apps/frontend, where tsx is installed)
 *   npx tsx ../../tools/compare_rule_engines.mjs             # check
 *   npx tsx ../../tools/compare_rule_engines.mjs --update    # re-baseline
 *
 * `--update` rewrites the expectation. Only run it when a behaviour change is
 * intended, and READ THE DIFF it prints before committing — that diff is the
 * whole safety review.
 *
 * Exits non-zero on any unexpected difference, so it can gate CI.
 */

import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const EXPECTED_PATH = join(__dirname, "rule_engine_expected.json");
const UPDATE = process.argv.includes("--update");

// pathToFileURL, not a bare path: on Windows an absolute path starts "C:\",
// which the ESM loader reads as a URL scheme named "c" and rejects.
const { evaluate, explain, nextFollowup, requiredFollowups } = await import(
  pathToFileURL(join(ROOT, "apps/frontend/convex/ai/ruleEngine/rules.ts")).href
);

/**
 * The corpus. Read from the frozen Python capture purely for its task list —
 * the same 579 unique (description, category) pairs — so the two eras cover
 * identical inputs and remain comparable.
 */
const corpus = JSON.parse(
  readFileSync(join(__dirname, "rule_engine_python_results.json"), "utf-8"),
);

/** Deep equality for the plain JSON shapes we compare. */
function eq(a, b) {
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((x, i) => eq(x, b[i]));
  }
  return a === b;
}

/**
 * The four answer states. `all_unsure` was added with the three-valued answers:
 * "not sure" must escalate like no answer at all, and only an exhaustive replay
 * shows that holds for every task rather than the one that was spot-checked.
 */
function answerStates(fields) {
  return {
    none: {},
    all_yes: Object.fromEntries(fields.map((f) => [f, true])),
    all_no: Object.fromEntries(fields.map((f) => [f, false])),
    mixed: Object.fromEntries(fields.map((f, i) => [f, i % 2 === 0])),
    all_unsure: Object.fromEntries(fields.map((f) => [f, "unsure"])),
  };
}

/** Run the engine over the whole corpus and return the full result set. */
function run() {
  const results = [];

  for (const row of corpus) {
    const base = { description: row.task_text, category: row.category };
    const baseFields = requiredFollowups({ ...base, followupAnswers: {} });
    const states = {};

    for (const [state, answers] of Object.entries(answerStates(baseFields))) {
      const input = { ...base, followupAnswers: answers };
      const { risk, triggered } = evaluate(input);
      states[state] = {
        risk,
        triggered,
        explanations: explain(triggered),
        required: requiredFollowups(input),
        next: nextFollowup(input),
      };
    }

    results.push({
      id: row.id ?? "",
      task_text: row.task_text,
      category: row.category,
      states,
    });
  }
  return results;
}

const actual = run();
const evaluationCount = actual.length * Object.keys(actual[0].states).length;

if (UPDATE) {
  writeFileSync(EXPECTED_PATH, JSON.stringify(actual, null, 1), "utf-8");
  console.log(`re-baselined ${EXPECTED_PATH}`);
  console.log(`  ${actual.length} rows x ${evaluationCount / actual.length} states ` +
    `= ${evaluationCount} evaluations`);
  console.log("\n⚠️  Review the git diff of that file before committing — it is the");
  console.log("    record of exactly which risk levels this change moved.");
  process.exit(0);
}

let expected;
try {
  expected = JSON.parse(readFileSync(EXPECTED_PATH, "utf-8"));
} catch {
  console.error(`No baseline at ${EXPECTED_PATH}. Create it with --update.`);
  process.exit(1);
}

const byKey = new Map(expected.map((r) => [`${r.task_text}||${r.category}`, r]));
const mismatches = [];

for (const row of actual) {
  const want = byKey.get(`${row.task_text}||${row.category}`);
  if (!want) {
    mismatches.push({
      task: row.task_text,
      category: row.category,
      state: "-",
      field: "row",
      expected: "(absent from baseline)",
      actual: "(present)",
    });
    continue;
  }

  for (const [state, got] of Object.entries(row.states)) {
    const wantState = want.states[state];
    if (!wantState) continue;
    for (const field of ["risk", "triggered", "explanations", "required", "next"]) {
      if (!eq(got[field], wantState[field])) {
        mismatches.push({
          task: row.task_text,
          category: row.category,
          state,
          field,
          expected: wantState[field],
          actual: got[field],
        });
      }
    }
  }
}

console.log(`compared ${evaluationCount} evaluations across ${actual.length} rows`);

if (mismatches.length === 0) {
  console.log("\n✅ PASS — rule engine behaviour matches the reviewed baseline.");
  process.exit(0);
}

console.error(`\n❌ FAIL — ${mismatches.length} unexpected difference(s).\n`);
console.error("If this change was intended, re-run with --update and review the diff.\n");
for (const m of mismatches.slice(0, 25)) {
  console.error(`  [${m.state}] ${m.field}  —  "${m.task}" (${m.category})`);
  console.error(`      baseline: ${JSON.stringify(m.expected)}`);
  console.error(`      now:      ${JSON.stringify(m.actual)}`);
}
if (mismatches.length > 25) {
  console.error(`\n  ... and ${mismatches.length - 25} more.`);
}
process.exit(1);
