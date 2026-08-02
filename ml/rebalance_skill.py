"""Break the user_skill / risk_level confound in the seed dataset.

Run: python ml/rebalance_skill.py [--apply]

WHAT THIS DOES, AND WHAT IT DELIBERATELY DOES NOT
--------------------------------------------------
It reassigns `user_skill` and nothing else. No `risk_level`, no `risk_label`,
no `hazards`, no `task_text`, no follow-up is touched. Not one safety
judgement is altered.

That restraint is the point. The confound could in principle be fixed from
either side — correct the labels that were set with an eye on the narrator,
or correct the narrator. Correcting labels would mean re-judging 256
hand-authored safety assessments against no domain-expert baseline
(ml/data/REVIEW.md), substituting one person's judgement at scale for
another's. Correcting the annotation changes nothing anyone relied on.

WHY REASSIGNING user_skill IS SAFE HERE
---------------------------------------
Measured before writing this: **zero** of the 256 seed `task_text` values
mention the narrator's experience in any form. `user_skill` was chosen "to
fit the narrative" of each example (memory.md, 2026-07-29) and has no anchor
in the text, so a row that reads "install a new consumer unit" is equally
coherent whoever is asking. Under the labelling rule in ml/data/README.md
that is exactly as it should be: `risk_level` describes what the TASK
demands, and who is asking never moves it.

THE CONFOUND BEING FIXED
------------------------
Across all 555 rows, 77 of the 85 `Experienced` rows (91%) were level 4, and
levels 1-3 contained no `Experienced` example at all. The classifier learned
that faithfully and returned level 4 for an experienced user changing a light
bulb while returning level 1 for a beginner rewiring a consumer unit.

METHOD
------
Round-robin assignment within each risk level, over rows sorted by `id`.
Deterministic - no RNG, so the result is identical on every machine and every
re-run, and the diff is reviewable. Every generated variant then inherits its
parent's new skill, because all 299 already tracked their parent exactly.

Prints a before/after contingency table and the normalised mutual
information. Writes nothing unless `--apply` is passed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

DATA = Path(__file__).parent / "data"
SEEDS = DATA / "seed_examples.json"
GENERATED = DATA / "generated_examples.json"

SKILLS = ("Beginner", "Some experience", "Experienced")


def nmi(rows: list[dict]) -> float:
    """Normalised mutual information between user_skill and risk_level."""
    n = len(rows)
    if not n:
        return 0.0

    def entropy(counts) -> float:
        return -sum((c / n) * math.log(c / n) for c in counts if c)

    h_skill = entropy(Counter(r["user_skill"] for r in rows).values())
    h_level = entropy(Counter(r["risk_level"] for r in rows).values())
    h_joint = entropy(Counter((r["user_skill"], r["risk_level"]) for r in rows).values())
    denom = min(h_skill, h_level)
    return (h_skill + h_level - h_joint) / denom if denom else 0.0


def table(rows: list[dict], title: str) -> None:
    print(f"\n{title}")
    print(f"{'':10}" + "".join(f"{s[:14]:>17}" for s in SKILLS) + f"{'total':>8}")
    for level in range(1, 6):
        counts = [
            sum(1 for r in rows if r["risk_level"] == level and r["user_skill"] == s)
            for s in SKILLS
        ]
        print(f"{'level ' + str(level):10}" + "".join(f"{c:>17}" for c in counts) + f"{sum(counts):>8}")
    totals = [sum(1 for r in rows if r["user_skill"] == s) for s in SKILLS]
    print(f"{'total':10}" + "".join(f"{t:>17}" for t in totals))
    print(f"  normalised mutual information: {nmi(rows):.3f}")


def main() -> int:
    apply = "--apply" in sys.argv
    seeds = json.loads(SEEDS.read_text(encoding="utf-8"))
    generated = json.loads(GENERATED.read_text(encoding="utf-8"))

    table(seeds + generated, "BEFORE (all 555 rows)")

    # Round-robin within each level, over a stable sort, so the assignment is
    # reproducible and the resulting diff can be reviewed line by line.
    changed = 0
    for level in range(1, 6):
        group = sorted(
            (r for r in seeds if r["risk_level"] == level), key=lambda r: str(r.get("id", ""))
        )
        for i, row in enumerate(group):
            new = SKILLS[i % len(SKILLS)]
            if row["user_skill"] != new:
                changed += 1
            row["user_skill"] = new

    # Variants already tracked their parent's skill exactly (299/299); keep
    # that true, or a paraphrase would disagree with the row it came from.
    by_id = {r["id"]: r for r in seeds if "id" in r}
    propagated = 0
    for variant in generated:
        parent = by_id.get(variant.get("variant_of"))
        if parent and variant["user_skill"] != parent["user_skill"]:
            variant["user_skill"] = parent["user_skill"]
            propagated += 1

    table(seeds + generated, "AFTER")
    print(f"\nseed rows whose user_skill changed : {changed}/{len(seeds)}")
    print(f"generated variants re-synced       : {propagated}/{len(generated)}")
    print("risk_level / risk_label / hazards / task_text changed: 0 (by construction)")

    if not apply:
        print("\nDry run. Re-run with --apply to write ml/data/*.json.")
        return 0

    SEEDS.write_text(json.dumps(seeds, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    GENERATED.write_text(
        json.dumps(generated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"\nwrote {SEEDS} and {GENERATED}")
    print("next: python ml/validate_dataset.py && python ml/make_splits.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
