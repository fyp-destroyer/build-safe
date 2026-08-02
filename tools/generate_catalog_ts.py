"""Generate the TypeScript safety catalog from the Python one.

WHY THIS EXISTS
---------------
`ai/rule_engine/catalog.py` is ~1000 lines of pure DATA: 33 hazard rules, their
floors, keywords, excludes, gates and user-facing explanations. When the backend
moved to Convex (TypeScript), that data had to move with it.

Hand-transcribing it was not an acceptable option. A dropped keyword or a floor
typed as 3 instead of 4 does not fail a build, does not throw at runtime, and
does not look wrong on review — it just silently under-escalates one hazard
family forever. Generating the TypeScript from the Python source removes that
entire class of error: the two cannot disagree, because one is derived from the
other.

USAGE (one-off, re-run only if the catalog ever changes)
--------------------------------------------------------
    cd apps/backend
    python ../../tools/generate_catalog_ts.py

Writes apps/frontend/convex/ai/ruleEngine/catalog.ts.

This script runs at BUILD time on a developer machine, never at request time —
the deployed system is TypeScript-only, with no Python anywhere.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

# Import the catalog as the backend sees it.
BACKEND = Path(__file__).resolve().parents[1] / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from ai.rule_engine.catalog import (  # noqa: E402
    FOLLOWUPS,
    HARD_GATE_RULE_IDS,
    LLM_SELECTABLE_FOLLOWUP_FIELDS,
    MAX_RISK_LEVEL,
    MIN_RISK_LEVEL,
    _RULES,
)

OUT = (
    Path(__file__).resolve().parents[1]
    / "apps"
    / "frontend"
    / "convex"
    / "ai"
    / "ruleEngine"
    / "catalog.ts"
)

HEADER = '''/**
 * The hardcoded safety rule catalog.
 *
 * ⚠️  GENERATED FILE — DO NOT EDIT BY HAND.
 *     Source:    apps/backend/ai/rule_engine/catalog.py
 *     Generator: tools/generate_catalog_ts.py
 *
 * This module is DATA, not logic. It is the single source of truth for which
 * hazards exist, what each one escalates risk to, and how each is explained to
 * a user. `rules.ts` evaluates it; nothing else may define a hazard.
 *
 * NON-NEGOTIABLE CONSTRAINTS (rules.md §4, CLAUDE.md):
 *
 *   * This catalog is hardcoded and version-controlled. There is deliberately
 *     no `safetyRules` table, no admin UI, and no runtime edit path — changing
 *     a rule means a code change and a code review (srs.md §2.5, §9).
 *   * Every rule can only ever RAISE risk to its `floor`. No rule may lower a
 *     risk level. Callers combine via finalRisk = max(ml, rules).
 *   * The LLM may only ever SELECT rule ids from this set (hazard tagging). It
 *     cannot invent a rule, cannot assign a risk number, and cannot change a
 *     floor. Any id it returns that is not a key of RULES is discarded.
 *
 * JURISDICTION: rules are written in terms of hazard and consequence, not
 * citations to any specific regulation. Thresholds like "gas work requires a
 * professional" are near-universal, but the exact licensing regime differs by
 * country, and this project does not target one — so no rule claims legal
 * authority it cannot back.
 */

/** One hazard rule.
 *
 *  `floor` is the minimum risk level a job matching this rule may receive. It
 *  is a floor, never a ceiling and never an assignment: the engine takes the
 *  maximum across triggered rules, and the caller takes the maximum of that and
 *  the ML prediction.
 */
export interface Rule {
  id: string;
  hazard: string;
  floor: number;
  summary: string;
  explanation: string;
  keywords: readonly string[];
  /** Negative keywords: presence of any means the rule does NOT fire. */
  excludes: readonly string[];
  categories: readonly string[];
  /** If set, fires only for these userSkill values. No rule uses this today
   *  (skill was retired 2026-08-02) but the gate is still enforced. */
  requiresSkill: readonly string[];
  /** Follow-up fields whose CONFIRMED-SAFE answer (true) means this hazard does
   *  not apply, so the rule never fires.
   *
   *  This is NOT de-escalation. A gate refines the TRIGGER CONDITION — it is
   *  `excludes` sourced from a user answer rather than from text — and nothing
   *  lowers a risk level that was already assigned. The safety property that
   *  makes it sound is the default: an UNANSWERED gate still fires the rule, so
   *  the worst plausible case holds until the user rules it out. Silence never
   *  buys a lower risk level; only an explicit answer does. */
  gatedBy: readonly string[];
}

/** A question whose answer materially changes risk.
 *
 *  MISSING and "no" are different states and escalate differently. Missing
 *  scores HIGHER: an explicit "no" is a known state a user can be advised
 *  about, whereas an unanswered safety question means the worst case cannot be
 *  ruled out at all (CLAUDE.md: "treat as worst plausible case, never assume
 *  safety"). Conflating the two once made the entire dangerous-task path
 *  unreachable — see memory.md, 2026-07-19.
 */
export interface Followup {
  field: string;
  question: string;
  floorWhenMissing: number;
  floorWhenDenied: number;
  appliesWhenRule: readonly string[];
  /** Deliberately unused. Category triggering asked nonsense once real
   *  categories arrived ("is the wall load-bearing?" for a flat-pack wardrobe).
   *  Follow-ups are driven by which HAZARD RULE fired, which is the precise
   *  signal. Kept so a future follow-up can opt in explicitly. */
  appliesToCategories: readonly string[];
}

export const MIN_RISK_LEVEL = %(min)d;
export const MAX_RISK_LEVEL = %(max)d;
'''

FOOTER = '''
export const RULES: Readonly<Record<string, Rule>> = Object.freeze(
  Object.fromEntries(RULE_LIST.map((r) => [r.id, r])),
);

/** The closed set the LLM hazard tagger may choose from. Anything outside this
 *  is discarded — it is a model error, never a new rule. */
export const VALID_RULE_IDS: ReadonlySet<string> = new Set(RULE_LIST.map((r) => r.id));

export const FOLLOWUPS_BY_FIELD: Readonly<Record<string, Followup>> = Object.freeze(
  Object.fromEntries(FOLLOWUPS.map((f) => [f.field, f])),
);

/** Hazards that no user answer may ever gate away.
 *
 *  `Rule.gatedBy` is right for facts the user is authoritative about (can you
 *  reach it?). It is wrong for these: a user is not a reliable judge of whether
 *  a gas escape, live conductor or asbestos exposure is really happening, and
 *  the cost of believing them wrongly is somebody's life. Enforced by a test,
 *  not just by convention. */
export const HARD_GATE_RULE_IDS: ReadonlySet<string> = new Set(%(hard_gates)s);

/** Follow-up fields the LLM may ASK FOR on its own initiative.
 *
 *  Purely ADDITIVE: the LLM cannot invent a question, and cannot suppress one —
 *  whatever `requiredFollowups()` derives from the fired hazards is asked
 *  regardless. This lets the tagger say "the description is ambiguous about
 *  height, ask about it" instead of resolving that ambiguity by guessing a tag. */
export const LLM_SELECTABLE_FOLLOWUP_FIELDS: ReadonlySet<string> = new Set(%(selectable)s);
'''

# Python field name -> TypeScript field name.
RULE_KEYS = [
    ("id", "id"),
    ("hazard", "hazard"),
    ("floor", "floor"),
    ("summary", "summary"),
    ("explanation", "explanation"),
    ("keywords", "keywords"),
    ("excludes", "excludes"),
    ("categories", "categories"),
    ("requires_skill", "requiresSkill"),
    ("gated_by", "gatedBy"),
]

FOLLOWUP_KEYS = [
    ("field", "field"),
    ("question", "question"),
    ("floor_when_missing", "floorWhenMissing"),
    ("floor_when_denied", "floorWhenDenied"),
    ("applies_when_rule", "appliesWhenRule"),
    ("applies_to_categories", "appliesToCategories"),
]


def js(value) -> str:
    """Serialize a Python value as a TypeScript literal.

    json.dumps is used rather than str() so that quotes, backslashes and any
    non-ASCII characters in the user-facing explanation text survive exactly.
    """
    if isinstance(value, (tuple, list)):
        if not value:
            return "[]"
        inner = ", ".join(json.dumps(v, ensure_ascii=False) for v in value)
        return f"[{inner}]"
    return json.dumps(value, ensure_ascii=False)


def emit_object(obj, keys, indent="  ") -> str:
    data = asdict(obj)
    lines = [f"{indent}{{"]
    for py_key, ts_key in keys:
        lines.append(f"{indent}  {ts_key}: {js(data[py_key])},")
    lines.append(f"{indent}}},")
    return "\n".join(lines)


def main() -> int:
    parts = [HEADER % {"min": MIN_RISK_LEVEL, "max": MAX_RISK_LEVEL}]

    parts.append("\nconst RULE_LIST: readonly Rule[] = [")
    for rule in _RULES:
        parts.append(emit_object(rule, RULE_KEYS))
    parts.append("];\n")

    parts.append("export const FOLLOWUPS: readonly Followup[] = [")
    for f in FOLLOWUPS:
        parts.append(emit_object(f, FOLLOWUP_KEYS))
    parts.append("];\n")

    parts.append(
        FOOTER
        % {
            "hard_gates": js(sorted(HARD_GATE_RULE_IDS)),
            "selectable": js(sorted(LLM_SELECTABLE_FOLLOWUP_FIELDS)),
        }
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(parts), encoding="utf-8")

    print(f"wrote {OUT}")
    print(f"  {len(_RULES)} rules, {len(FOLLOWUPS)} follow-ups")
    print(f"  {len(HARD_GATE_RULE_IDS)} hard-gated rule ids")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
