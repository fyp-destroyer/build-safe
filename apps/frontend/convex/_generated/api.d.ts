/* eslint-disable */
/**
 * Generated `api` utility.
 *
 * THIS CODE IS AUTOMATICALLY GENERATED.
 *
 * To regenerate, run `npx convex dev`.
 * @module
 */

import type * as ai_classifier_classify from "../ai/classifier/classify.js";
import type * as ai_classifier_tfidf from "../ai/classifier/tfidf.js";
import type * as ai_jobLogic from "../ai/jobLogic.js";
import type * as ai_llm_client from "../ai/llm/client.js";
import type * as ai_ruleEngine_catalog from "../ai/ruleEngine/catalog.js";
import type * as ai_ruleEngine_catalogBasis from "../ai/ruleEngine/catalogBasis.js";
import type * as ai_ruleEngine_llmAssist from "../ai/ruleEngine/llmAssist.js";
import type * as ai_ruleEngine_rules from "../ai/ruleEngine/rules.js";
import type * as assessments from "../assessments.js";
import type * as chat from "../chat.js";
import type * as http from "../http.js";
import type * as jobs from "../jobs.js";
import type * as recommendations from "../recommendations.js";
import type * as users from "../users.js";

import type {
  ApiFromModules,
  FilterApi,
  FunctionReference,
} from "convex/server";

declare const fullApi: ApiFromModules<{
  "ai/classifier/classify": typeof ai_classifier_classify;
  "ai/classifier/tfidf": typeof ai_classifier_tfidf;
  "ai/jobLogic": typeof ai_jobLogic;
  "ai/llm/client": typeof ai_llm_client;
  "ai/ruleEngine/catalog": typeof ai_ruleEngine_catalog;
  "ai/ruleEngine/catalogBasis": typeof ai_ruleEngine_catalogBasis;
  "ai/ruleEngine/llmAssist": typeof ai_ruleEngine_llmAssist;
  "ai/ruleEngine/rules": typeof ai_ruleEngine_rules;
  assessments: typeof assessments;
  chat: typeof chat;
  http: typeof http;
  jobs: typeof jobs;
  recommendations: typeof recommendations;
  users: typeof users;
}>;

/**
 * A utility for referencing Convex functions in your app's public API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = api.myModule.myFunction;
 * ```
 */
export declare const api: FilterApi<
  typeof fullApi,
  FunctionReference<any, "public">
>;

/**
 * A utility for referencing Convex functions in your app's internal API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = internal.myModule.myFunction;
 * ```
 */
export declare const internal: FilterApi<
  typeof fullApi,
  FunctionReference<any, "internal">
>;

export declare const components: {};
