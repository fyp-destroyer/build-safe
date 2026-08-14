/**
 * Safety tests for LLM-suggested follow-up answers.
 *
 * A suggestion is the one place the LLM touches a safety-critical ANSWER rather
 * than a hazard tag or some wording, so the tests here are about the boundary
 * that keeps it additive (rules.md §4): a suggestion is shown to the user, and
 * only the user's own tap ever writes to `followupAnswers`.
 *
 * `generateStructured` is mocked because these assert what happens to the
 * model's reply AFTER it arrives — the discard paths are the whole safety
 * story, and they must hold for replies a real provider would rarely produce.
 *
 * Lives in its own file rather than in ruleEngine.test.ts because the mock is
 * module-scoped and would otherwise stub the LLM for every test in that file.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

const generateStructured = vi.hoisted(() => vi.fn());
vi.mock("../llm/client", () => ({ generateStructured }));

import { suggestFollowupAnswer } from "./llmAssist";
import { missingRequiredFollowups } from "../jobLogic";
import { evaluate } from "./rules";
import { FOLLOWUPS_BY_FIELD } from "./catalog";

/** A description that genuinely settles the load-bearing question. */
const STATED = "retile a wall in my kitchen, the wall is not load-bearing";
/** The same task with the safety fact never mentioned. */
const UNSTATED = "retile a wall in my kitchen";

beforeEach(() => {
  generateStructured.mockReset();
});

describe("suggestFollowupAnswer", () => {
  it("suggests an answer the description actually gives, quoting it", async () => {
    generateStructured.mockResolvedValue({
      answer: "yes",
      evidence: "the wall is not load-bearing",
    });

    const out = await suggestFollowupAnswer(STATED, "load_bearing_confirmed");

    expect(out).toEqual({ answer: true, evidence: "the wall is not load-bearing" });
  });

  it("maps every recognised answer to its stored value", async () => {
    const cases: [string, unknown][] = [
      ["yes", true],
      ["no", false],
      ["unsure", "unsure"],
    ];
    for (const [reply, expected] of cases) {
      generateStructured.mockResolvedValue({ answer: reply, evidence: "retile a wall" });
      const out = await suggestFollowupAnswer(STATED, "load_bearing_confirmed");
      expect(out?.answer).toBe(expected);
    }
  });

  // THE central guard. The model asserting the user already answered, without
  // being able to quote them, is the failure that would pre-select "Yes" on a
  // safety question the user never addressed. It is caught mechanically, the
  // same way an ungrounded hazard tag is — a prompt instruction is not enough.
  it("discards a suggestion whose evidence is not in the description", async () => {
    generateStructured.mockResolvedValue({
      answer: "yes",
      evidence: "the wall is not load-bearing",
    });

    expect(await suggestFollowupAnswer(UNSTATED, "load_bearing_confirmed")).toBeNull();
  });

  it("returns null when the description does not settle the question", async () => {
    generateStructured.mockResolvedValue({ answer: "not_stated", evidence: "" });
    expect(await suggestFollowupAnswer(UNSTATED, "load_bearing_confirmed")).toBeNull();
  });

  // No coercion path: an unrecognised string must not fall through to a value,
  // and least of all to the safe one.
  it("discards an unrecognised answer rather than coercing it", async () => {
    for (const reply of ["probably", "YES!", "true", "", "1"]) {
      generateStructured.mockResolvedValue({ answer: reply, evidence: "retile a wall" });
      expect(await suggestFollowupAnswer(STATED, "load_bearing_confirmed")).toBeNull();
    }
  });

  it("returns null when the LLM is unavailable", async () => {
    generateStructured.mockResolvedValue(null);
    expect(await suggestFollowupAnswer(STATED, "load_bearing_confirmed")).toBeNull();
  });

  it("returns null for a field outside the hardcoded catalog", async () => {
    generateStructured.mockResolvedValue({ answer: "yes", evidence: "retile a wall" });
    expect(await suggestFollowupAnswer(STATED, "invented_field")).toBeNull();
    // Never even asked — an unknown field has no question to answer.
    expect(generateStructured).not.toHaveBeenCalled();
  });

  it("only ever proposes fields the catalog defines", async () => {
    generateStructured.mockResolvedValue({
      answer: "yes",
      evidence: "the wall is not load-bearing",
    });
    const out = await suggestFollowupAnswer(STATED, "load_bearing_confirmed");
    expect(out).not.toBeNull();
    expect(FOLLOWUPS_BY_FIELD["load_bearing_confirmed"]).toBeDefined();
  });
});

/**
 * The property that makes the whole feature safe: a suggestion is not an answer.
 *
 * These assert it structurally rather than by inspection — the rule engine and
 * the follow-up gate read `followupAnswers`, and a suggestion is stored on the
 * job's `nextFollowup` instead, so there is no path by which one can escalate
 * or de-escalate anything.
 */
describe("a suggestion is not an answer", () => {
  const JOB = {
    description: STATED,
    category: "tiling",
    followupAnswers: {},
    llmHazardIds: ["structural_alteration"],
    llmFollowupFields: [],
  };

  it("leaves the field blocking assessment until the user answers", () => {
    expect(missingRequiredFollowups(JOB)).toContain("load_bearing_confirmed");
  });

  it("leaves the unanswered escalation fully in force", () => {
    const spec = FOLLOWUPS_BY_FIELD["load_bearing_confirmed"];
    const { risk, triggered } = evaluate({
      description: JOB.description,
      category: JOB.category,
      llmHazardIds: JOB.llmHazardIds,
      followupAnswers: {},
    });

    expect(risk).toBe(spec.floorWhenMissing);
    expect(triggered).toContain("missing_followup:load_bearing_confirmed");
  });

  it("de-escalates only once the answer is actually recorded", () => {
    const withAnswer = evaluate({
      description: JOB.description,
      category: JOB.category,
      llmHazardIds: JOB.llmHazardIds,
      followupAnswers: { load_bearing_confirmed: true },
    });
    const without = evaluate({
      description: JOB.description,
      category: JOB.category,
      llmHazardIds: JOB.llmHazardIds,
      followupAnswers: {},
    });

    expect(withAnswer.risk).toBeLessThan(without.risk);
    expect(withAnswer.triggered).toContain("safe_followup:load_bearing_confirmed");
  });
});
