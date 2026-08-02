/**
 * Port equivalence gate: TypeScript rule engine vs the Python one.
 *
 * Reads `rule_engine_python_results.json` (written by
 * tools/dump_python_rule_results.py), replays every row through the TypeScript
 * engine, and fails loudly on ANY difference.
 *
 * This is the check that licenses deleting apps/backend. A rule engine port is
 * not the kind of thing you eyeball: a dropped keyword or a floor typed as 3
 * instead of 4 compiles, runs, and looks fine on review — it just silently
 * under-escalates one hazard family forever. Comparing every row under every
 * answer state is the only way to know the two agree.
 *
 * WHAT IS COMPARED (all four, per row per answer state)
 *   risk         — the escalation floor
 *   triggered    — exact rule ids, order included
 *   explanations — the user-facing safety text
 *   required     — which follow-ups the engine derives
 *   next         — which one it would ask next
 *
 * Risk level alone would be far too weak: two engines can agree on 3 while
 * disagreeing about which hazards produced it, which is the failure that matters.
 *
 * USAGE (from apps/frontend, which is where tsx is installed)
 *   npx tsx ../../tools/compare_rule_engines.mjs
 *
 * Run through tsx rather than plain node: the engine under test is TypeScript,
 * and tsx transpiles it on import so no build step is needed.
 *
 * Exits non-zero on any mismatch, so it can gate CI.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

// pathToFileURL, not a bare path: on Windows an absolute path starts "C:\",
// which the ESM loader reads as a URL scheme named "c" and rejects.
const { evaluate, explain, nextFollowup, requiredFollowups } = await import(
  pathToFileURL(join(ROOT, "apps/frontend/convex/ai/ruleEngine/rules.ts")).href
);

const expected = JSON.parse(
  readFileSync(join(__dirname, "rule_engine_python_results.json"), "utf-8"),
);

/** Deep equality for the plain JSON shapes we compare (arrays, strings, numbers, null). */
function eq(a, b) {
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((x, i) => eq(x, b[i]));
  }
  return a === b;
}

function answerStates(fields) {
  return {
    none: {},
    all_yes: Object.fromEntries(fields.map((f) => [f, true])),
    all_no: Object.fromEntries(fields.map((f) => [f, false])),
    mixed: Object.fromEntries(fields.map((f, i) => [f, i % 2 === 0])),
  };
}

let checked = 0;
const mismatches = [];

for (const row of expected) {
  const base = {
    description: row.task_text,
    category: row.category,
    userSkill: row.user_skill,
  };

  // Derive the follow-up set with no answers, exactly as the Python side did,
  // so the two build identical answer states.
  const baseFields = requiredFollowups({ ...base, followupAnswers: {} });

  for (const [state, answers] of Object.entries(answerStates(baseFields))) {
    const want = row.states[state];
    const input = { ...base, followupAnswers: answers };

    const { risk, triggered } = evaluate(input);
    const got = {
      risk,
      triggered,
      explanations: explain(triggered),
      required: requiredFollowups(input),
      next: nextFollowup(input),
    };

    for (const field of ["risk", "triggered", "explanations", "required", "next"]) {
      if (!eq(got[field], want[field])) {
        mismatches.push({
          id: row.id || row.task_text.slice(0, 40),
          task: row.task_text,
          category: row.category,
          state,
          field,
          python: want[field],
          typescript: got[field],
        });
      }
    }
    checked += 1;
  }
}

console.log(`compared ${checked} evaluations across ${expected.length} rows`);

if (mismatches.length === 0) {
  console.log("\n✅ PASS — the TypeScript engine is identical to the Python engine.");
  process.exit(0);
}

console.error(`\n❌ FAIL — ${mismatches.length} mismatch(es).\n`);
for (const m of mismatches.slice(0, 25)) {
  console.error(`  [${m.state}] ${m.field}  —  "${m.task}" (${m.category})`);
  console.error(`      python:     ${JSON.stringify(m.python)}`);
  console.error(`      typescript: ${JSON.stringify(m.typescript)}`);
}
if (mismatches.length > 25) {
  console.error(`\n  ... and ${mismatches.length - 25} more.`);
}
process.exit(1);
