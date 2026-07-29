"""Phase 2 step 5: build the train/val/test split.

Writes ml/data/{train,val,test}.json (70/15/15).

The whole point of this script is the grouping. A generated variant shares
almost all its text with its parent seed, and a few seeds are deliberate
near-duplicates of each other (same task, differing only in what the user
states). Splitting rows independently would put the same task in train and
test, and every downstream metric would be inflated by memorisation.

So: rows are grouped, groups are assigned to splits atomically, and the
script then verifies no near-duplicate pair survives across two splits.

Deterministic - no RNG, ordering is by id.

Run: python ml/make_splits.py
"""

from __future__ import annotations

import difflib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

DATA = Path(__file__).parent / "data"
RATIOS = {"train": 0.70, "val": 0.15, "test": 0.15}

# Seeds this similar to each other are treated as one unit.
SEED_MERGE_THRESHOLD = 0.72
# Post-split leak check: no pair this similar may straddle two splits.
LEAK_THRESHOLD = 0.85

# Sequence ratio alone is not enough. The deliberate contrast sets are built
# by ADDING a clause to a base task ("install a ceiling fan in my bedroom"
# vs the same plus "- I already switched off the breaker..."), and the length
# disparity drags the ratio down to ~0.41 even though one text wholly
# contains the other. Containment catches exactly that shape.
CONTAINMENT_THRESHOLD = 0.9
MIN_TOKENS_FOR_CONTAINMENT = 4


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def related(a: str, b: str) -> bool:
    """True if two task_texts describe the same underlying task."""
    if difflib.SequenceMatcher(None, a, b).ratio() >= SEED_MERGE_THRESHOLD:
        return True
    ta, tb = tokens(a), tokens(b)
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if len(short) < MIN_TOKENS_FOR_CONTAINMENT:
        return False
    return len(short & long_) / len(short) >= CONTAINMENT_THRESHOLD


class Union:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def main() -> int:
    seeds = json.loads((DATA / "seed_examples.json").read_text(encoding="utf-8"))
    generated = json.loads((DATA / "generated_examples.json").read_text(encoding="utf-8"))

    rows = []
    for e in seeds:
        rows.append({**e, "source": "seed", "_base": e["id"]})
    for g in generated:
        rows.append({**g, "source": "generated", "_base": g["variant_of"]})

    # --- grouping -------------------------------------------------------
    uf = Union()
    for r in rows:
        uf.union(r["id"], r["_base"])

    # Merge seeds that are near-duplicates of one another (the deliberate
    # "same task, different stated information" pairs).
    merged_pairs = []
    for i in range(len(seeds)):
        for j in range(i + 1, len(seeds)):
            if related(seeds[i]["task_text"], seeds[j]["task_text"]):
                uf.union(seeds[i]["id"], seeds[j]["id"])
                merged_pairs.append((seeds[i]["id"], seeds[j]["id"],
                                     seeds[i]["task_text"][:38]))

    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[uf.find(r["id"])].append(r)

    print(f"{len(rows)} rows -> {len(groups)} groups "
          f"({len(merged_pairs)} near-duplicate seed pair(s) merged)")
    for a, b, t in merged_pairs:
        print(f"    merged {a} + {b}  ({t}...)")

    # --- stratified assignment -----------------------------------------
    # Each group is stratified by its most severe risk_level, so the rarest
    # and most safety-relevant classes are the ones kept balanced.
    by_stratum: dict[int, list[tuple[str, list[dict]]]] = defaultdict(list)
    for gid, members in groups.items():
        by_stratum[max(m["risk_level"] for m in members)].append((gid, members))

    assigned: dict[str, str] = {}
    for stratum in sorted(by_stratum):
        entries = sorted(by_stratum[stratum], key=lambda kv: kv[0])
        total = sum(len(m) for _, m in entries)
        targets = {s: total * ratio for s, ratio in RATIOS.items()}
        counts = dict.fromkeys(RATIOS, 0)
        # Largest groups first: they constrain the ratios most.
        for gid, members in sorted(entries, key=lambda kv: (-len(kv[1]), kv[0])):
            split = max(RATIOS, key=lambda s: targets[s] - counts[s])
            assigned[gid] = split
            counts[split] += len(members)

    splits: dict[str, list[dict]] = {s: [] for s in RATIOS}
    for gid, members in groups.items():
        for m in sorted(members, key=lambda r: r["id"]):
            row = {k: v for k, v in m.items() if k != "_base"}
            row["group_id"] = gid
            splits[assigned[gid]].append(row)

    for s in splits:
        splits[s].sort(key=lambda r: r["id"])

    # --- verification ---------------------------------------------------
    problems: list[str] = []

    where = {}
    for s, rws in splits.items():
        for r in rws:
            if r["group_id"] in where and where[r["group_id"]] != s:
                problems.append(f"group {r['group_id']} spans {where[r['group_id']]} and {s}")
            where[r["group_id"]] = s

    for s, rws in splits.items():
        present = {r["risk_level"] for r in rws}
        if present != {1, 2, 3, 4, 5}:
            problems.append(f"{s} is missing risk level(s) {sorted({1,2,3,4,5} - present)}")
        if not any(r["source"] == "seed" for r in rws):
            problems.append(f"{s} contains no hand-written examples")

    if sum(len(v) for v in splits.values()) != len(rows):
        problems.append("row count mismatch after splitting")

    # Cross-split leak check, on SEED texts only.
    #
    # A generated row cannot leak on its own: it is always grouped with the
    # seed it came from, so its split is its parent's split. Comparing
    # generated text directly also produces false alarms, because every
    # rephrase shares a template wrapper ("I was going to ... from an
    # extension ladder"), which inflates the similarity of two genuinely
    # different underlying tasks. The seed text is the real task identity,
    # so that is what gets checked.
    tagged = [(s, r) for s, rws in splits.items() for r in rws if r["source"] == "seed"]
    leaks = 0
    for i in range(len(tagged)):
        si, ri = tagged[i]
        for j in range(i + 1, len(tagged)):
            sj, rj = tagged[j]
            if si == sj:
                continue
            if related(ri["task_text"], rj["task_text"]):
                leaks += 1
                if leaks <= 5:
                    problems.append(
                        f"LEAK {si}/{sj}: {ri['task_text'][:45]!r} ~ {rj['task_text'][:45]!r}")

    # --- report ---------------------------------------------------------
    print()
    for s in ("train", "val", "test"):
        rws = splits[s]
        pct = len(rws) / len(rows) * 100
        seedn = sum(1 for r in rws if r["source"] == "seed")
        print(f"{s:5s} {len(rws):4d} rows ({pct:4.1f}%)  "
              f"{seedn:3d} hand-written / {len(rws) - seedn:3d} generated  "
              f"risk={dict(sorted(Counter(r['risk_level'] for r in rws).items()))}")

    if problems:
        print(f"\n{len(problems)} PROBLEM(S)" + (f" ({leaks} leaks total)" if leaks else "") + ":")
        for p in problems[:12]:
            print(f"  - {p}")
        return 1

    for s, rws in splits.items():
        (DATA / f"{s}.json").write_text(json.dumps(rws, indent=2) + "\n", encoding="utf-8")
    print("\nNo group spans splits; no cross-split near-duplicates; all classes present.")
    print("Wrote train.json / val.json / test.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
