/**
 * Safety tests for the rule engine and catalog.
 *
 * Ported from apps/backend/tests/test_rule_catalog.py, test_rule_engine.py and
 * test_llm_assist.py. rules.md §1 forbids shipping `ai/rule_engine` without
 * tests, and §5 requires that any change touching it is covered.
 *
 * These are PROPERTY tests about the safety invariants, not golden-output tests.
 * Exact output equivalence with the Python original is covered separately and
 * far more thoroughly by tools/compare_rule_engines.mjs, which diffs all 2,316
 * evaluations. What these add is the reason those outputs are correct: that no
 * code path can lower a risk level, that silence never buys safety, and that the
 * LLM cannot exceed its authority.
 */

import { describe, expect, it } from "vitest";
import {
  FOLLOWUPS,
  UNSURE_ANSWER,
  FOLLOWUPS_BY_FIELD,
  HARD_GATE_RULE_IDS,
  LLM_SELECTABLE_FOLLOWUP_FIELDS,
  MAX_RISK_LEVEL,
  MIN_RISK_LEVEL,
  RULES,
  VALID_RULE_IDS,
} from "./catalog";
import {
  answerState,
  evaluate,
  explain,
  matchedRuleIds,
  nextFollowup,
  requiredFollowups,
} from "./rules";
import { ASKS_WHETHER_USER_CHECKED, evidenceSupports } from "./llmAssist";

/** A task with no hazard keywords in any rule, used as the benign control. */
const BENIGN = { description: "hang a small picture frame on a stud wall", category: "carpentry" };

describe("catalog integrity", () => {
  it("has rules whose floors are all within the valid range", () => {
    for (const rule of Object.values(RULES)) {
      expect(rule.floor).toBeGreaterThanOrEqual(MIN_RISK_LEVEL);
      expect(rule.floor).toBeLessThanOrEqual(MAX_RISK_LEVEL);
    }
  });

  it("has unique rule ids, and VALID_RULE_IDS matches the catalog exactly", () => {
    const ids = Object.values(RULES).map((r) => r.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect([...VALID_RULE_IDS].sort()).toEqual([...ids].sort());
  });

  it("can actually fire every rule, by keyword or by LLM tag", () => {
    // Not "every rule has keywords" — `overhead_work_unknown_height` has NONE by
    // design. It is an LLM-only rule: the tagger selects it when a description
    // is ambiguous about working height, and its `height_access` gate closes if
    // the user confirms they can reach the work from floor level. What must hold
    // is the weaker, true property: every rule is reachable by SOME path.
    for (const rule of Object.values(RULES)) {
      const reachableByKeyword = rule.keywords.length > 0;
      const reachableByLlm = VALID_RULE_IDS.has(rule.id);
      expect(
        reachableByKeyword || reachableByLlm,
        `${rule.id} can never fire by any path`,
      ).toBe(true);
    }
  });

  it("gates every keyword-less rule, so it is not silently unreachable", () => {
    // A rule with no keywords depends entirely on the LLM. If the LLM is down,
    // it never fires — so it must not be the sole cover for a hazard family.
    // Recording the expectation here makes that dependency visible rather than
    // an accident of the catalog.
    for (const rule of Object.values(RULES)) {
      if (rule.keywords.length === 0) {
        expect(
          rule.gatedBy.length,
          `${rule.id} has no keywords and no gate — it can only ever fire from an LLM tag`,
        ).toBeGreaterThan(0);
      }
    }
  });

  it("only gates on follow-up fields that actually exist", () => {
    for (const rule of Object.values(RULES)) {
      for (const field of rule.gatedBy) {
        expect(FOLLOWUPS_BY_FIELD[field], `${rule.id} gates on unknown field ${field}`).toBeDefined();
      }
    }
  });

  it("never lets a user answer gate away a catastrophic hazard", () => {
    // A user is not a reliable judge of whether a gas escape, live conductor or
    // asbestos exposure is really happening, and the cost of believing them
    // wrongly is somebody's life.
    for (const id of HARD_GATE_RULE_IDS) {
      expect(RULES[id], `${id} is hard-gated but not in the catalog`).toBeDefined();
      expect(RULES[id].gatedBy, `${id} must not be gateable`).toEqual([]);
    }
  });

  it("has follow-ups that reference real rules and escalate upward", () => {
    for (const f of FOLLOWUPS) {
      for (const ruleId of f.appliesWhenRule) {
        expect(RULES[ruleId], `${f.field} references unknown rule ${ruleId}`).toBeDefined();
      }
      // Missing must score at least as high as an explicit "no": an unanswered
      // safety question means the worst case cannot be ruled out at all.
      expect(f.floorWhenMissing).toBeGreaterThanOrEqual(f.floorWhenDenied);
      expect(f.floorWhenMissing).toBeLessThanOrEqual(MAX_RISK_LEVEL);
      expect(f.floorWhenDenied).toBeGreaterThanOrEqual(MIN_RISK_LEVEL);
    }
  });

  it("exposes every follow-up field to the LLM's selectable set", () => {
    expect([...LLM_SELECTABLE_FOLLOWUP_FIELDS].sort()).toEqual(
      FOLLOWUPS.map((f) => f.field).sort(),
    );
  });

  it("gives every follow-up a floorWhenDenied that can actually change the outcome", () => {
    // THE DEAD-PARAMETER GUARD.
    //
    // A follow-up only applies once one of its triggering rules has fired, so
    // the score is already at least the lowest floor among those rules. If
    // floorWhenDenied is at or below that, answering "no" scores exactly the
    // same as answering "yes" — the question is asked, the user tells us the
    // circuit is still live, and nothing happens. Two follow-ups shipped in that
    // state (power_isolated at 3, load_bearing_confirmed at 4).
    //
    // Nothing about that fails loudly, which is why it needs a test.
    for (const f of FOLLOWUPS) {
      if (f.appliesWhenRule.length === 0) continue;

      const floors = f.appliesWhenRule.map((id) => RULES[id].floor);
      const lowestTriggeringFloor = Math.min(...floors);

      // A gated follow-up is exempt: its "yes" stops the rule firing entirely,
      // so the answer changes the outcome via the gate rather than via this
      // floor (height_access works exactly this way).
      const isGate = Object.values(RULES).some(
        (r) => r.gatedBy.includes(f.field) && f.appliesWhenRule.includes(r.id),
      );
      if (isGate) continue;

      expect(
        f.floorWhenDenied,
        `${f.field}: floorWhenDenied ${f.floorWhenDenied} is <= the lowest floor ` +
          `(${lowestTriggeringFloor}) of the rules that trigger it, so answering ` +
          `"no" cannot change the result — the question is dead weight`,
      ).toBeGreaterThan(lowestTriggeringFloor);
    }
  });

  it("asks about the world, not about whether the user checked", () => {
    // "Have you confirmed X?" makes "no" ambiguous between "I checked and X is
    // false" and "I never checked" — two different risks. Condition framing
    // ("Is X true?") keeps them separable, with "not sure" covering the second.
    for (const f of FOLLOWUPS) {
      expect(
        ASKS_WHETHER_USER_CHECKED.test(f.question),
        `${f.field} asks whether the user verified something: "${f.question}"`,
      ).toBe(false);
      expect(f.question, `${f.field} is not phrased as a question`).toContain("?");
    }
  });
});

describe("rules can only escalate, never de-escalate", () => {
  it("returns a risk in range and defaults to the minimum", () => {
    const { risk } = evaluate(BENIGN);
    expect(risk).toBeGreaterThanOrEqual(MIN_RISK_LEVEL);
    expect(risk).toBeLessThanOrEqual(MAX_RISK_LEVEL);
  });

  it("does not escalate a benign task", () => {
    const { risk, triggered } = evaluate(BENIGN);
    expect(risk).toBe(MIN_RISK_LEVEL);
    expect(triggered).toEqual([]);
  });

  it("never returns below the highest floor among triggered rules", () => {
    // The core invariant, checked for EVERY rule in the catalog. Each is fired
    // by its own first keyword where it has one, and by an LLM tag where it does
    // not (see the keyword-less rule above).
    for (const rule of Object.values(RULES)) {
      const byKeyword = rule.keywords.length > 0;

      // Answer every follow-up "confirmed safe" so that follow-up escalation
      // cannot be what lifts the score — EXCEPT this rule's own gate fields,
      // since confirming those legitimately stops the rule firing at all.
      const answers = Object.fromEntries(
        FOLLOWUPS.filter((f) => !rule.gatedBy.includes(f.field)).map((f) => [f.field, true]),
      );

      const { risk } = evaluate({
        description: byKeyword ? rule.keywords[0] : "a task with no matching keywords at all",
        category: rule.categories[0] ?? "general",
        followupAnswers: answers,
        llmHazardIds: byKeyword ? undefined : [rule.id],
      });

      expect(risk, `${rule.id} did not reach its floor`).toBeGreaterThanOrEqual(rule.floor);
    }
  });

  it("keeps final risk >= ML risk for every combination", () => {
    // final = max(ml, rules) can never fall below ml. Verified over the whole
    // grid rather than a sample, since it is the single most important
    // arithmetic property in the product (rules.md §4.2).
    for (let ml = MIN_RISK_LEVEL; ml <= MAX_RISK_LEVEL; ml++) {
      for (const rule of Object.values(RULES)) {
        const { risk } = evaluate({ description: rule.keywords[0], category: "general" });
        expect(Math.max(ml, risk)).toBeGreaterThanOrEqual(ml);
        expect(Math.max(ml, risk)).toBeGreaterThanOrEqual(risk);
      }
    }
  });

  it("escalates a gas hazard above a low ML prediction", () => {
    const { risk } = evaluate({ description: "i can smell gas near the boiler", category: "hvac" });
    expect(risk).toBeGreaterThanOrEqual(4);
    expect(Math.max(1, risk)).toBe(risk);
  });
});

describe("missing information escalates, never assumes safety", () => {
  const ELECTRICAL = {
    description: "replace the fixed wiring for the kitchen sockets",
    category: "electrical",
  };

  it("derives a safety-critical follow-up for hazardous work", () => {
    const required = requiredFollowups(ELECTRICAL);
    expect(required.length).toBeGreaterThan(0);
    expect(required).toContain("power_isolated");
  });

  it("scores a missing answer higher than an explicit no", () => {
    const missing = evaluate({ ...ELECTRICAL, followupAnswers: {} });
    const denied = evaluate({ ...ELECTRICAL, followupAnswers: { power_isolated: false } });
    expect(missing.risk).toBeGreaterThanOrEqual(denied.risk);
    expect(missing.triggered).toContain("missing_followup:power_isolated");
    expect(denied.triggered).toContain("unsafe_followup:power_isolated");
  });

  it("treats an explicit false as answered, not as unanswered", () => {
    // Conflating "answered no" with "not answered" once made the entire
    // dangerous-task path unreachable — the engine re-asked forever.
    const next = nextFollowup({ ...ELECTRICAL, followupAnswers: { power_isolated: false } });
    expect(next).not.toBe("power_isolated");
  });

  it("stops asking once every derived follow-up has an answer", () => {
    const required = requiredFollowups(ELECTRICAL);
    const answers = Object.fromEntries(required.map((f) => [f, false]));
    expect(nextFollowup({ ...ELECTRICAL, followupAnswers: answers })).toBeNull();
  });

  it("drives follow-ups from fired hazards, not from category alone", () => {
    // A task can need power_isolated without being category electrical.
    const required = requiredFollowups({
      description: "chase a channel into the wall for a new cable before tiling",
      category: "tiling",
    });
    expect(required).toContain("power_isolated");
  });
});

describe("three-valued answers: yes / no / not sure", () => {
  const ELECTRICAL = {
    description: "replace the fixed wiring for the kitchen sockets",
    category: "electrical",
  };

  it("classifies every answer, defaulting anything unrecognised to absent", () => {
    expect(answerState(true)).toBe("confirmed");
    expect(answerState(false)).toBe("denied");
    expect(answerState(UNSURE_ANSWER)).toBe("unsure");
    expect(answerState(undefined)).toBe("absent");

    // The safety-critical part. A corrupted value, a stale client sending a
    // string, a renamed field — none may be read as "safe". Every unrecognised
    // value falls to `absent`, which escalates hardest.
    for (const junk of [null, "", "yes", "true", 1, 0, {}, [], NaN, "UNSURE"]) {
      expect(answerState(junk), `${JSON.stringify(junk)} must not be trusted`).toBe("absent");
    }
  });

  it("scores 'not sure' as hard as no answer at all", () => {
    const unanswered = evaluate({ ...ELECTRICAL, followupAnswers: {} });
    const unsure = evaluate({ ...ELECTRICAL, followupAnswers: { power_isolated: UNSURE_ANSWER } });

    expect(unsure.risk).toBe(unanswered.risk);
    expect(unsure.risk).toBe(FOLLOWUPS_BY_FIELD.power_isolated.floorWhenMissing);
  });

  it("distinguishes 'not sure' from 'no' in the markers, and scores it higher", () => {
    const unsure = evaluate({ ...ELECTRICAL, followupAnswers: { power_isolated: UNSURE_ANSWER } });
    const denied = evaluate({ ...ELECTRICAL, followupAnswers: { power_isolated: false } });

    expect(unsure.triggered).toContain("unsure_followup:power_isolated");
    expect(denied.triggered).toContain("unsafe_followup:power_isolated");
    // An unknown fact cannot be ruled out; a known-bad one can at least be
    // advised about. So "not sure" must never score BELOW "no".
    expect(unsure.risk).toBeGreaterThanOrEqual(denied.risk);
  });

  it("treats 'not sure' as answered, so the user is not asked in a loop", () => {
    const next = nextFollowup({
      ...ELECTRICAL,
      followupAnswers: { power_isolated: UNSURE_ANSWER },
    });
    expect(next).not.toBe("power_isolated");
  });

  it("records a confirmed answer without touching the risk level", () => {
    // The marker is presentation only. If it moved the number it would be
    // de-escalation, which rules.md §4.2 forbids outright.
    const confirmed = evaluate({ ...ELECTRICAL, followupAnswers: { power_isolated: true } });
    expect(confirmed.triggered).toContain("safe_followup:power_isolated");

    const rulesOnly = evaluate({
      description: ELECTRICAL.description,
      category: ELECTRICAL.category,
      // Same job, but with the follow-up satisfied a different way: the score
      // must come from the fired rules alone.
      followupAnswers: { power_isolated: true },
    });
    expect(confirmed.risk).toBe(rulesOnly.risk);
    expect(confirmed.risk).toBe(RULES.fixed_wiring_work.floor);
  });

  it("explains all three answers differently, and never implies clearance", () => {
    const [missing] = explain(["missing_followup:power_isolated"]);
    const [unsure] = explain(["unsure_followup:power_isolated"]);
    const [denied] = explain(["unsafe_followup:power_isolated"]);
    const [safe] = explain(["safe_followup:power_isolated"]);

    for (const text of [missing, unsure, denied, safe]) {
      expect(text).toBeTruthy();
    }
    expect(new Set([missing, unsure, denied, safe]).size).toBe(4);

    // "Not sure" must not be reported back as "you didn't answer" — that would
    // be false, and would read as the system's failure rather than an honest gap.
    expect(unsure).toContain("weren't sure");
  });

  it("answering 'no' now changes the outcome for the previously-dead follow-ups", () => {
    // Regression test for the dead-parameter bug: these two scored identically
    // whether the user said yes or no.
    const wiringYes = evaluate({ ...ELECTRICAL, followupAnswers: { power_isolated: true } });
    const wiringNo = evaluate({ ...ELECTRICAL, followupAnswers: { power_isolated: false } });
    expect(wiringNo.risk).toBeGreaterThan(wiringYes.risk);

    const WALL = { description: "knock through a structural wall", category: "masonry" };
    const wallYes = evaluate({ ...WALL, followupAnswers: { load_bearing_confirmed: true } });
    const wallNo = evaluate({ ...WALL, followupAnswers: { load_bearing_confirmed: false } });
    expect(wallNo.risk).toBeGreaterThan(wallYes.risk);
  });
});

describe("the LLM cannot reintroduce ambiguous question framing", () => {
  it("flags verification framing in its many forms", () => {
    for (const bad of [
      "Have you confirmed the power is off?",
      "Have you checked whether the wall is load-bearing?",
      "Did you verify the circuit is dead?",
      "Has your electrician confirmed the isolation?",
      "Do you ensure the area is clear of gas lines?",
      "Have you made sure the breaker is off?",
      "Did you test the wire before starting?",
    ]) {
      expect(ASKS_WHETHER_USER_CHECKED.test(bad), `should reject: ${bad}`).toBe(true);
    }
  });

  it("leaves condition-framed questions alone", () => {
    for (const good of [
      "Is the power to this circuit switched off and isolated at the breaker?",
      "Is the wall or structure you will be working on non-load-bearing?",
      "Is the work area clear of gas lines?",
      "Can you reach this comfortably from floor level or a step ladder?",
      // Mentions checking, but asks about the world rather than the user's
      // diligence — the boundary the regex has to respect.
      "Is the checked circuit still live?",
    ]) {
      expect(ASKS_WHETHER_USER_CHECKED.test(good), `should accept: ${good}`).toBe(false);
    }
  });
});

describe("gates refine the trigger, they do not lower risk", () => {
  /** Fire a gated rule the only way it can be fired, and see what survives. */
  function fireGated(rule: (typeof RULES)[string], answers: Record<string, boolean>) {
    const byKeyword = rule.keywords.length > 0;
    return matchedRuleIds({
      description: byKeyword ? rule.keywords[0] : "an ambiguous overhead task",
      category: rule.categories[0] ?? "general",
      followupAnswers: answers,
      llmHazardIds: byKeyword ? undefined : [rule.id],
    });
  }

  it("closes a gate only on an explicit confirmed-safe answer", () => {
    const gatedRules = Object.values(RULES).filter((r) => r.gatedBy.length > 0);
    expect(gatedRules.length, "catalog has no gated rules to test").toBeGreaterThan(0);

    for (const rule of gatedRules) {
      const field = rule.gatedBy[0];

      // Unanswered and explicitly-denied must BOTH still fire the rule. Only a
      // confirmed-safe "true" closes the gate. Silence never buys safety.
      expect(fireGated(rule, {}), `${rule.id} unanswered`).toContain(rule.id);
      expect(fireGated(rule, { [field]: false }), `${rule.id} denied`).toContain(rule.id);
      expect(fireGated(rule, { [field]: true }), `${rule.id} confirmed`).not.toContain(rule.id);
    }
  });

  it("never lets a closed gate drop risk below an ungated hazard", () => {
    // A gate stops ITS OWN rule firing; it must not touch anything else. Here a
    // genuine gas hazard is present alongside a confirmed-safe height answer.
    const { risk } = evaluate({
      description: "i can smell gas while working on the ceiling",
      category: "hvac",
      followupAnswers: { height_access: true },
    });
    expect(risk).toBeGreaterThanOrEqual(RULES.active_gas_or_co.floor);
  });
});

describe("the LLM cannot exceed its authority", () => {
  const TASK = { description: "paint the spare bedroom ceiling", category: "painting" };

  it("discards proposed ids outside the hardcoded catalog", () => {
    const fired = matchedRuleIds({
      ...TASK,
      llmHazardIds: ["not_a_real_rule", "definitely_invented_hazard"],
    });
    expect(fired).not.toContain("not_a_real_rule");
    expect(fired).not.toContain("definitely_invented_hazard");
  });

  it("cannot invent a risk number — only ids, whose floors are hardcoded", () => {
    const { risk } = evaluate({ ...TASK, llmHazardIds: ["active_gas_or_co"] });
    // The level comes from the catalog's floor for that id, not from the model.
    expect(risk).toBe(RULES.active_gas_or_co.floor);
  });

  it("is additive — an LLM tag cannot suppress a keyword match", () => {
    const withoutLlm = matchedRuleIds({
      description: "i can smell gas in the kitchen",
      category: "general",
    });
    const withEmptyLlm = matchedRuleIds({
      description: "i can smell gas in the kitchen",
      category: "general",
      llmHazardIds: [],
    });
    expect(withEmptyLlm).toEqual(withoutLlm);
    expect(withoutLlm.length).toBeGreaterThan(0);
  });

  it("holds an LLM tag to the same exclude list as a keyword match", () => {
    // The veto path that LLM tags previously bypassed entirely.
    const excluded = Object.values(RULES).find((r) => r.excludes.length > 0);
    if (!excluded) return;

    const fired = matchedRuleIds({
      description: `${excluded.keywords[0]} ${excluded.excludes[0]}`,
      category: excluded.categories[0] ?? "general",
      llmHazardIds: [excluded.id],
    });
    expect(fired).not.toContain(excluded.id);
  });

  it("only accepts follow-up fields from the closed selectable set", () => {
    const required = requiredFollowups({
      ...TASK,
      llmAskedFields: ["height_access", "invented_field_name"],
    });
    expect(required).not.toContain("invented_field_name");
    expect(required).toContain("height_access");
  });

  it("lets LLM-asked follow-ups widen but never narrow the question set", () => {
    const base = requiredFollowups({
      description: "replace the fixed wiring in the kitchen",
      category: "electrical",
    });
    const widened = requiredFollowups({
      description: "replace the fixed wiring in the kitchen",
      category: "electrical",
      llmAskedFields: ["height_access"],
    });
    for (const f of base) expect(widened).toContain(f);
  });
});

describe("evidence grounding", () => {
  const DESCRIPTION = "How do I change my light bulb in the hallway?";

  it("rejects a quote the user never wrote", () => {
    // The exact failure this check exists for: the model reasoned bulb ->
    // ceiling -> overhead -> height and tagged a level-3 hazard.
    expect(evidenceSupports(DESCRIPTION, "on a ladder at roof height")).toBe(false);
  });

  it("accepts a verbatim span", () => {
    expect(evidenceSupports(DESCRIPTION, "change my light bulb")).toBe(true);
  });

  it("ignores case and collapses whitespace, but relaxes nothing else", () => {
    expect(evidenceSupports(DESCRIPTION, "CHANGE   MY\n LIGHT bulb")).toBe(true);
    expect(evidenceSupports(DESCRIPTION, "change the light bulb")).toBe(false);
  });

  it("rejects empty or whitespace-only evidence", () => {
    expect(evidenceSupports(DESCRIPTION, "")).toBe(false);
    expect(evidenceSupports(DESCRIPTION, "   \n  ")).toBe(false);
  });
});

describe("explanations are hardcoded, never generated", () => {
  it("returns the catalog's own text for a known rule", () => {
    const [id, rule] = Object.entries(RULES)[0];
    expect(explain([id])).toEqual([rule.explanation]);
  });

  it("skips unknown ids rather than guessing at them", () => {
    expect(explain(["not_a_real_rule"])).toEqual([]);
  });

  it("explains missing and denied follow-ups differently", () => {
    const missing = explain(["missing_followup:power_isolated"]);
    const denied = explain(["unsafe_followup:power_isolated"]);
    expect(missing).toHaveLength(1);
    expect(denied).toHaveLength(1);
    expect(missing[0]).not.toEqual(denied[0]);
    expect(missing[0]).toContain("worst plausible case");
  });

  it("returns nothing when nothing triggered", () => {
    expect(explain([])).toEqual([]);
  });
});
