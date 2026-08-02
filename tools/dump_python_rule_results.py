"""Run the PYTHON rule engine over every dataset row and dump the results.

Half of the port equivalence gate. `tools/compare_rule_engines.mjs` runs the
TypeScript engine over the same rows and diffs against this file's output.

WHY A FILE INSTEAD OF ONE SCRIPT
--------------------------------
The two engines are in different languages and runtimes, so they cannot be
compared in-process. Dumping the Python side to JSON lets the comparison be
re-run against the TypeScript side at any time — including after `apps/backend`
is deleted, at which point this file becomes the frozen record of what the
Python engine did, and the only remaining evidence that the port was faithful.

WHAT IS COMPARED
----------------
For every row: the risk level, the exact triggered-rule list (order included),
the derived follow-up fields, and the next unanswered follow-up. Risk level alone
would be far too weak a check — two engines can agree on 3 while disagreeing about
which hazards produced it, which is the failure that matters.

Each row is evaluated under FOUR follow-up answer states, because most of the
engine's escalation logic lives in the difference between them:

  none    - no answers at all (missing -> worst plausible case)
  all_yes - every derived follow-up confirmed safe (exercises gates)
  all_no  - every derived follow-up denied      (exercises floor_when_denied)
  mixed   - alternating, so a partially-answered job is covered too

USAGE
-----
    python tools/dump_python_rule_results.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "backend"))

from ai.rule_engine.rules import (  # noqa: E402
    evaluate,
    explain,
    next_followup,
    required_followups,
)

DATA = ROOT / "ml" / "data"
OUT = ROOT / "tools" / "rule_engine_python_results.json"


def load_rows() -> list[dict]:
    """Every row we can get, from all sources, de-duplicated by (text, category).

    Uses the raw seed + generated sets rather than the train/val/test splits so
    the comparison covers the full corpus regardless of how it was split, plus
    the pre-committed holdout cases which were written specifically to probe
    rule behaviour.
    """
    rows: list[dict] = []

    for name in ("seed_examples.json", "generated_examples.json", "holdout_rules.json"):
        path = DATA / name
        if not path.exists():
            print(f"  (skipping missing {name})")
            continue
        for item in json.loads(path.read_text(encoding="utf-8")):
            rows.append(
                {
                    "source": name,
                    "id": item.get("id", ""),
                    "task_text": item["task_text"],
                    "category": item.get("category", "general"),
                    "user_skill": item.get("user_skill", ""),
                }
            )

    seen: set[tuple[str, str]] = set()
    unique: list[dict] = []
    for r in rows:
        key = (r["task_text"], r["category"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique


def answer_states(fields: list[str]) -> dict[str, dict]:
    return {
        "none": {},
        "all_yes": {f: True for f in fields},
        "all_no": {f: False for f in fields},
        "mixed": {f: (i % 2 == 0) for i, f in enumerate(fields)},
    }


def main() -> int:
    rows = load_rows()
    print(f"loaded {len(rows)} unique rows")

    results = []
    for r in rows:
        desc, cat, skill = r["task_text"], r["category"], r["user_skill"]

        # Derive the follow-up set with no answers, then use it to build the
        # answer states. Deriving it per-state would change what is being asked
        # as answers arrive, which is correct behaviour but makes the states
        # incomparable.
        base_fields = required_followups(desc, cat, None, skill, {})

        per_state = {}
        for state, answers in answer_states(base_fields).items():
            risk, triggered = evaluate(desc, cat, answers, None, skill, None)
            per_state[state] = {
                "risk": risk,
                "triggered": triggered,
                "explanations": explain(triggered),
                "required": required_followups(desc, cat, None, skill, answers, None),
                "next": next_followup(desc, cat, answers, None, skill, None),
            }

        results.append(
            {
                "id": r["id"],
                "source": r["source"],
                "task_text": desc,
                "category": cat,
                "user_skill": skill,
                "states": per_state,
            }
        )

    OUT.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")

    total = len(results) * 4
    escalated = sum(
        1 for r in results for s in r["states"].values() if s["risk"] > 1
    )
    print(f"wrote {OUT}")
    print(f"  {len(results)} rows x 4 answer states = {total} evaluations")
    print(f"  {escalated} evaluations escalated above level 1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
