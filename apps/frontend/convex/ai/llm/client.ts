/**
 * LLM client wrapper — Gemini or Groq, behind one function.
 *
 * **THIS IS THE ONLY MODULE IN THE ENTIRE CODEBASE THAT CALLS AN LLM.** Every
 * other module that needs an LLM-assisted answer must go through
 * `generateStructured` below — never call a provider endpoint anywhere else.
 *
 * Ported from apps/backend/ai/llm/client.py. The Python version used the
 * `google-genai` SDK for Gemini; this one uses plain `fetch` against the REST
 * endpoint for both providers, so the module runs in Convex's default V8 runtime
 * with no Node-only dependencies and no vendor SDK.
 *
 * STRUCTURAL ENFORCEMENT OF THE BOUNDARY
 * --------------------------------------
 * In the Python backend, "only this module calls an LLM" was a convention held
 * up by a docstring. Here it is also enforced by the runtime: network I/O is
 * only legal inside a Convex **action**, so a query or mutation physically
 * cannot reach a model. The risk arithmetic in ai/ruleEngine/ lives in
 * mutations and pure functions, and therefore cannot consult an LLM even by
 * mistake.
 *
 * Boundary (rules.md §4 / CLAUDE.md, non-negotiable):
 *   - The LLM is template/schema-constrained only. `generateStructured` forces
 *     the model into structured JSON matching a caller-supplied Zod schema — it
 *     is never allowed to return free text that gets trusted as-is. Whatever
 *     comes back is validated against that schema before any caller sees it, on
 *     every provider.
 *   - The LLM is NEVER used to emit a risk level, invent a hazard rule, or
 *     invent a category outside a fixed, code-reviewed closed set. Its only
 *     permitted jobs anywhere in this codebase are: (a) phrasing follow-up
 *     question text for an already-hardcoded field, (b) turning already-
 *     triggered rules into templated explanation text, and (c) tagging which
 *     member of a fixed category/rule set a task's text matches. See
 *     ai/ruleEngine/llmAssist.ts — the only caller of this module.
 *   - This function never throws. Any failure (network error, missing/invalid
 *     API key, timeout, rate limit, malformed/unparseable response) is caught,
 *     logged as a warning, and surfaced as `null`. Every caller MUST treat
 *     `null` as "LLM unavailable" and fall back to a hardcoded, safe default —
 *     this module succeeding is never load-bearing for safety, only for
 *     wording/tagging convenience.
 *
 * CHOOSING A PROVIDER
 * -------------------
 * `LLM_PROVIDER` = "gemini" | "groq" | "auto" (default), with `GEMINI_API_KEY` /
 * `GROQ_API_KEY` supplying credentials, all set in the Convex dashboard. "auto"
 * uses whichever key is set and prefers Gemini when both are, so adding a Groq
 * key never silently changes an existing setup — set `LLM_PROVIDER=groq` to
 * actually switch.
 *
 * Because both providers are confined to the schema-constrained jobs listed
 * above, and every reply is validated before use, which provider is configured
 * cannot change any risk decision. A weaker model degrades tagging/wording
 * quality, and an invalid reply degrades to the same `null` (hardcoded fallback)
 * path as an outage. Neither can escalate, de-escalate, or invent a rule — that
 * arithmetic lives entirely in ai/ruleEngine/ and never consults this module.
 */

import { z } from "zod";

const GROQ_URL = "https://api.groq.com/openai/v1/chat/completions";
const GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models";
const TIMEOUT_MS = 20_000;

/**
 * Models observed to reject json_schema structured output, remembered for the
 * life of the isolate. Without this, a model that doesn't support it (e.g.
 * llama-3.3-70b-versatile) costs a wasted 400 on EVERY call before the
 * json_object retry — two HTTP round trips per tag. Learned at runtime rather
 * than hardcoded because Groq's per-model support changes and a stale list would
 * be worse than no list.
 */
const groqNoJsonSchema = new Set<string>();

const JSON_INSTRUCTION =
  "Respond with a single JSON object and nothing else — no prose, no " +
  "markdown fences. It must validate against this JSON Schema:\n";

type Provider = "gemini" | "groq" | null;

/** Which provider to call, or null if unconfigured. */
function resolveProvider(): Provider {
  const choice = (process.env.LLM_PROVIDER ?? "auto").trim().toLowerCase();
  const gemini = process.env.GEMINI_API_KEY;
  const groq = process.env.GROQ_API_KEY;

  if (choice === "gemini") return gemini ? "gemini" : null;
  if (choice === "groq") return groq ? "groq" : null;
  if (choice !== "auto") {
    console.warn(
      `Unknown LLM_PROVIDER=${JSON.stringify(choice)}; expected 'gemini', 'groq' ` +
        `or 'auto'. Falling back to auto-detection.`,
    );
  }

  // auto: prefer the incumbent, so adding a second key is never a silent switch
  // of which model is answering.
  if (gemini) return "gemini";
  if (groq) return "groq";
  return null;
}

/** fetch with a hard timeout — a hung provider must not hold an action open. */
async function fetchWithTimeout(url: string, init: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Make a Zod-generated JSON Schema acceptable to strict structured output:
 * every object must list all its properties as required and forbid extras.
 * Walks nested definitions rather than only fixing the top level.
 */
function strictify(schema: unknown): unknown {
  if (schema === null || typeof schema !== "object") return schema;
  if (Array.isArray(schema)) return schema.map(strictify);

  const out: Record<string, unknown> = { ...(schema as Record<string, unknown>) };

  if (out.type === "object" || "properties" in out) {
    const props = (out.properties ?? {}) as Record<string, unknown>;
    out.properties = Object.fromEntries(
      Object.entries(props).map(([k, v]) => [k, strictify(v)]),
    );
    out.required = Object.keys(props);
    out.additionalProperties = false;
  }
  if ("items" in out) out.items = strictify(out.items);
  for (const key of ["$defs", "definitions"]) {
    if (out[key] && typeof out[key] === "object") {
      out[key] = Object.fromEntries(
        Object.entries(out[key] as Record<string, unknown>).map(([k, v]) => [k, strictify(v)]),
      );
    }
  }
  return out;
}

/**
 * Strip JSON-Schema keywords Gemini's `responseSchema` rejects.
 *
 * Gemini accepts an OpenAPI 3.0 subset — type/properties/required/items/enum/
 * description/nullable — and 400s on `$schema`, `$defs`, `$ref`,
 * `additionalProperties` and friends. Zod emits several of those, so they are
 * removed here rather than hand-writing a second copy of every schema.
 */
function geminiSchema(schema: unknown): unknown {
  if (schema === null || typeof schema !== "object") return schema;
  if (Array.isArray(schema)) return schema.map(geminiSchema);

  const allowed = new Set([
    "type",
    "properties",
    "required",
    "items",
    "enum",
    "description",
    "nullable",
    "format",
  ]);

  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(schema as Record<string, unknown>)) {
    if (!allowed.has(k)) continue;
    out[k] = k === "properties"
      ? Object.fromEntries(
          Object.entries(v as Record<string, unknown>).map(([pk, pv]) => [pk, geminiSchema(pv)]),
        )
      : geminiSchema(v);
  }
  return out;
}

/**
 * Best-effort unwrap of a JSON object from a model reply.
 *
 * `json_object` mode is supposed to return bare JSON, but that mode is the
 * fallback path for models WITHOUT server-side schema enforcement — exactly the
 * models most likely to wrap the object in ```json fences or prefix it with a
 * sentence. Rather than discard an otherwise-correct answer over packaging,
 * strip the wrapper and let Zod judge the contents.
 *
 * This normalises the TEXT ONLY. Schema validation still happens after, so it
 * cannot let a wrong-shaped object through — it only stops us failing on a
 * right-shaped one.
 */
function extractJson(content: string): string {
  let text = content.trim();
  if (text.startsWith("```")) {
    text = text.includes("\n") ? text.slice(text.indexOf("\n") + 1) : text;
    if (text.trimEnd().endsWith("```")) {
      text = text.trimEnd().slice(0, -3);
    }
    text = text.trim();
  }
  if (!text.startsWith("{")) {
    const start = text.indexOf("{");
    const end = text.lastIndexOf("}");
    if (start !== -1 && end > start) text = text.slice(start, end + 1);
  }
  return text;
}

/** Parse + validate, returning null rather than throwing. */
function validate<T>(schema: z.ZodType<T>, raw: string): T | null {
  try {
    return schema.parse(JSON.parse(raw));
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Gemini
// ---------------------------------------------------------------------------

async function geminiGenerate<T>(
  prompt: string,
  schema: z.ZodType<T>,
  jsonSchema: unknown,
): Promise<T | null> {
  const key = process.env.GEMINI_API_KEY;
  if (!key) {
    console.warn("Gemini unavailable (no GEMINI_API_KEY); returning null.");
    return null;
  }

  // NOT gemini-2.5-flash by default: it still appears in models.list() but
  // generateContent rejects it for keys created after its retirement ("no longer
  // available to new users", HTTP 404), so the whole LLM layer silently fell back
  // to its hardcoded defaults. Found only by reading the actual API error — the
  // fallbacks are so well-behaved that nothing looked broken from outside. Hence
  // the model name is configuration, not code.
  const model = process.env.GEMINI_MODEL || "gemini-3.1-flash-lite";

  let response: Response;
  try {
    response = await fetchWithTimeout(`${GEMINI_URL}/${model}:generateContent?key=${key}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contents: [{ parts: [{ text: prompt }] }],
        generationConfig: {
          responseMimeType: "application/json",
          responseSchema: geminiSchema(jsonSchema),
          // Deterministic: these are tagging/phrasing calls, not creative ones.
          temperature: 0,
        },
      }),
    });
  } catch (err) {
    // Include the reason: "call failed" alone can't distinguish a dead key from
    // an exhausted quota (429) from a retired model (404), and this layer's
    // fallbacks are quiet enough that the log is the only signal.
    console.warn(
      `Gemini API call failed (${(err as Error).name}: ` +
        `${String((err as Error).message).slice(0, 200)}); caller must use its ` +
        `hardcoded fallback.`,
    );
    return null;
  }

  if (!response.ok) {
    console.warn(
      `Gemini API returned HTTP ${response.status} ` +
        `(${(await response.text().catch(() => "")).slice(0, 200)}); caller must ` +
        `use its hardcoded fallback.`,
    );
    return null;
  }

  let text: string;
  try {
    const body = (await response.json()) as {
      candidates?: { content?: { parts?: { text?: string }[] } }[];
    };
    text = body.candidates?.[0]?.content?.parts?.[0]?.text ?? "";
  } catch {
    console.warn("Gemini response had an unexpected shape; returning null.");
    return null;
  }

  const parsed = validate(schema, extractJson(text));
  if (parsed === null) {
    console.warn("Gemini response failed schema validation; returning null.");
  }
  return parsed;
}

// ---------------------------------------------------------------------------
// Groq (OpenAI-compatible chat completions)
// ---------------------------------------------------------------------------

/**
 * Request body for one Groq attempt.
 *
 * `strict` uses json_schema structured output, where the model is constrained
 * server-side. Otherwise the older json_object mode carries the schema in the
 * prompt instead — a fallback for models that reject json_schema (support varies
 * by model on Groq; llama-3.3-70b is one that does not take it). Either way the
 * reply is validated against the Zod schema before any caller sees it, so the
 * weaker mode cannot smuggle an off-schema value through — it only fails more
 * often, into the same hardcoded-fallback path as an outage.
 */
function groqPayload(
  prompt: string,
  name: string,
  jsonSchema: unknown,
  model: string,
  strict: boolean,
): Record<string, unknown> {
  const schema = strictify(jsonSchema);
  return {
    model,
    messages: [
      {
        role: "user",
        content: strict ? prompt : `${prompt}\n\n${JSON_INSTRUCTION}${JSON.stringify(schema)}`,
      },
    ],
    // Deterministic: these are tagging/phrasing calls, not creative ones.
    temperature: 0,
    response_format: strict
      ? { type: "json_schema", json_schema: { name, schema, strict: true } }
      : { type: "json_object" },
  };
}

async function groqGenerate<T>(
  prompt: string,
  schema: z.ZodType<T>,
  name: string,
  jsonSchema: unknown,
): Promise<T | null> {
  const key = process.env.GROQ_API_KEY;
  if (!key) {
    console.warn("Groq unavailable (no GROQ_API_KEY); returning null.");
    return null;
  }

  const model = process.env.GROQ_MODEL || "llama-3.3-70b-versatile";

  // Try server-side schema enforcement first, then degrade to json_object mode:
  // a 400 for an unsupported response_format is a model/config mismatch we can
  // recover from, not an outage. Once a model is known to reject it, skip
  // straight to the mode that works.
  const attempts = groqNoJsonSchema.has(model) ? [false] : [true, false];

  for (const strict of attempts) {
    let response: Response;
    try {
      response = await fetchWithTimeout(GROQ_URL, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${key}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(groqPayload(prompt, name, jsonSchema, model, strict)),
      });
    } catch (err) {
      console.warn(
        `Groq API call failed (${(err as Error).name}: ` +
          `${String((err as Error).message).slice(0, 200)}); caller must use its ` +
          `hardcoded fallback.`,
      );
      return null;
    }

    if (response.status === 400 && strict) {
      console.info(
        `Groq model ${JSON.stringify(model)} rejected json_schema structured ` +
          `output; using json_object mode for it from now on.`,
      );
      groqNoJsonSchema.add(model);
      continue;
    }

    if (response.status !== 200) {
      console.warn(
        `Groq API returned HTTP ${response.status} ` +
          `(${(await response.text().catch(() => "")).slice(0, 200)}); caller must ` +
          `use its hardcoded fallback.`,
      );
      return null;
    }

    let content: string;
    try {
      const body = (await response.json()) as {
        choices?: { message?: { content?: string } }[];
      };
      content = body.choices?.[0]?.message?.content ?? "";
    } catch {
      console.warn("Groq response had an unexpected shape; returning null.");
      return null;
    }

    const parsed = validate(schema, extractJson(content));
    if (parsed === null) {
      console.warn(
        `Groq response failed schema validation (${content.slice(0, 200)}); returning null.`,
      );
    }
    return parsed;
  }

  return null;
}

// ---------------------------------------------------------------------------
// Public entry point
// ---------------------------------------------------------------------------

/**
 * Call the configured LLM with a prompt, constrained to emit JSON matching
 * `schema`, and return a validated value.
 *
 * Returns null (never throws) if: no provider/API key is configured, the network
 * call fails for any reason, or the response can't be validated against `schema`.
 * Callers must always have a hardcoded fallback for the null case.
 *
 * @param name A stable name for the schema, used as the json_schema name Groq
 *             requires. Pass the conceptual type name, e.g. "HazardTags".
 */
export async function generateStructured<T>(
  prompt: string,
  schema: z.ZodType<T>,
  name: string,
): Promise<T | null> {
  const jsonSchema = z.toJSONSchema(schema);
  const provider = resolveProvider();

  if (provider === "gemini") return await geminiGenerate(prompt, schema, jsonSchema);
  if (provider === "groq") return await groqGenerate(prompt, schema, name, jsonSchema);

  console.warn("No LLM provider configured (set GEMINI_API_KEY or GROQ_API_KEY); returning null.");
  return null;
}
