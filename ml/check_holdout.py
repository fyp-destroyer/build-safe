"""Validate the rule engine against a held-out set it was never tuned on.

Run: python ml/check_holdout.py

`ml/data/holdout_rules.json` contains fresh tasks that appear nowhere in the
training data. It was written and committed BEFORE the rules it tests, so a
rule cannot have been fitted to it.

Half of it is adversarial NEGATIVES - superficially similar tasks that must
NOT escalate ("lean a ladder against the wall", "replace a rotten fence
post", "swap the faceplate on an existing socket"). Overfitting shows up as
an over-broad rule just as much as a narrow one, and positives alone would
not catch that: a rule keyed on the bare word "lean" or "rotten" scores
perfectly on positives and fails here.

Escalate means the rule engine alone reaches risk >= 4. The ML model is not
consulted - this measures the deterministic layer on its own, since that is
what the rules change.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "apps" / "backend"))

from ai.rule_engine import evaluate, required_followups  # noqa: E402

HOLDOUT = Path(__file__).parent / "data" / "holdout_rules.json"


def main() -> int:
    rows = json.loads(HOLDOUT.read_text(encoding="utf-8"))
    by_family: dict[str, list] = defaultdict(list)
    failures = []

    for r in rows:
        # Production always has required follow-ups answered before assessing
        # (assess_job 409s otherwise), so answer them safely. Escalation here
        # therefore comes from the hazard rules, not from a missing answer.
        answers = {
            f: True
            for f in required_followups(
                r["task_text"], r["category"], user_skill=r["user_skill"]
            )
        }
        risk, triggered = evaluate(
            r["task_text"], r["category"], answers, user_skill=r["user_skill"]
        )
        escalated = risk >= 4
        want = r["expect"] == "escalate"
        ok = escalated == want
        by_family[r["family"]].append(ok)
        if not ok:
            failures.append((r, risk, triggered, want))

    print("=" * 74)
    print("HELD-OUT RULE VALIDATION")
    print(f"  {HOLDOUT.name}: {len(rows)} fresh tasks, none in the training data")
    print("=" * 74)
    for fam, results in sorted(by_family.items()):
        passed = sum(results)
        print(f"  {fam:16s} {passed}/{len(results)} correct")

    pos = [r for r in rows if r["expect"] == "escalate"]
    neg = [r for r in rows if r["expect"] == "not_escalate"]
    print()
    npos_fail = sum(1 for f in failures if f[3])
    nneg_fail = sum(1 for f in failures if not f[3])
    print(f"  positives caught : {len(pos) - npos_fail}/{len(pos)}  "
          f"(missed hazards - the recall side)")
    print(f"  negatives held   : {len(neg) - nneg_fail}/{len(neg)}  "
          f"(false alarms - the over-broad side)")

    if failures:
        print(f"\n  {len(failures)} FAILURE(S):")
        for r, risk, triggered, want in failures:
            kind = "MISSED" if want else "FALSE ALARM"
            print(f"    [{kind}] risk={risk} {triggered}")
            print(f"      {r['task_text'][:66]}")
            print(f"      why it matters: {r['rationale']}")
        return 1

    print("\n  All held-out cases behave correctly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
