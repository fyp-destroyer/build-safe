import { Bot, Bug, ShieldCheck } from "lucide-react";

import type { DebugTrace } from "../types/assessment";

const SHOW_DEBUG_PANEL =
  !import.meta.env.PROD && import.meta.env.VITE_SHOW_DEBUG_PANEL === "true";

interface DeveloperTracePanelProps {
  trace?: DebugTrace | null;
}

export function DeveloperTracePanel({
  trace,
}: DeveloperTracePanelProps): JSX.Element | null {
  if (!SHOW_DEBUG_PANEL) {
    return null;
  }

  return (
    <section className="mt-4 min-w-0 rounded-[22px] border border-stone-200 bg-white p-4 shadow-sm sm:rounded-[24px] sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-stone-950 text-white">
            <Bug aria-hidden="true" className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
              Development only
            </p>
            <h4 className="text-base font-bold text-stone-950">Developer Trace</h4>
          </div>
        </div>

        <span className="inline-flex max-w-full items-center gap-2 rounded-full border border-stone-200 bg-stone-50 px-3 py-2 text-xs font-semibold text-stone-700">
          <Bot aria-hidden="true" className="h-4 w-4 text-amber-700" />
          <span className="min-w-0 break-words">{getLlmAssistLabel(trace)}</span>
        </span>
      </div>

      <details className="mt-4 rounded-[20px] border border-stone-200 bg-stone-50 px-4 py-3">
        <summary className="cursor-pointer text-sm font-semibold text-stone-900">
          Developer Trace
        </summary>

        {trace ? (
          <div className="mt-4 min-w-0 space-y-4">
            <div className="grid min-w-0 gap-3 md:grid-cols-2 xl:grid-cols-3">
              <TraceField label="Gemini enabled" value={toYesNo(trace.gemini_enabled)} />
              <TraceField label="Gemini used" value={toYesNo(trace.gemini_used)} />
              <TraceField label="Gemini model" value={trace.gemini_model} />
              <TraceField
                label="Gemini purpose"
                value={trace.gemini_used_for.length > 0 ? formatPurposeList(trace.gemini_used_for) : "Fallback only"}
              />
              <TraceField
                label="Task intent"
                value={trace.detected_task_intent ?? "Not available"}
              />
              <TraceField
                label="Task category"
                value={trace.detected_task_category ?? "Not available"}
              />
              <TraceField
                label="LLM suggested risk"
                value={trace.llm_suggested_risk_level ?? "Not available"}
              />
              <TraceField
                label="Rule engine risk"
                value={trace.rule_engine_risk_level ?? "Not available"}
              />
              <TraceField
                label="Final selected risk"
                value={trace.final_risk_level ?? "Not available"}
              />
              <TraceField label="Fallback used" value={toYesNo(trace.fallback_used)} />
              <TraceField
                label="Selected interpretation"
                value={trace.selected_interpretation || "Not available"}
              />
              <TraceField
                label="Gemini error"
                value={trace.gemini_error ?? "None"}
                tone={trace.gemini_error ? "warning" : "default"}
              />
            </div>

            <TraceList
              icon={ShieldCheck}
              title="Follow-up questions chosen"
              items={trace.follow_up_questions}
              emptyLabel="No follow-up questions were needed."
            />

            <TraceList
              icon={ShieldCheck}
              title="Rules triggered"
              items={trace.rules_triggered}
              emptyLabel="No rules were triggered."
            />

            <TraceList
              icon={ShieldCheck}
              title="Critical missing information"
              items={trace.critical_missing_info}
              emptyLabel="No critical unknowns remained."
            />

            <TraceList
              icon={ShieldCheck}
              title="Notes"
              items={trace.notes}
              emptyLabel="No extra debug notes were recorded."
            />

            {trace.parsed_llm_response || trace.llm_response_text || trace.llm_prompt ? (
              <details className="min-w-0 rounded-[18px] border border-stone-200 bg-white px-4 py-3">
                <summary className="cursor-pointer text-sm font-semibold text-stone-900">
                  Advanced LLM payload
                </summary>

                <div className="mt-4 min-w-0 space-y-4">
                  {trace.parsed_llm_response ? (
                    <TraceCodeBlock
                      title="Parsed LLM response"
                      content={JSON.stringify(trace.parsed_llm_response, null, 2)}
                    />
                  ) : null}

                  {trace.llm_response_text ? (
                    <TraceCodeBlock
                      title="Sanitized LLM response text"
                      content={trace.llm_response_text}
                    />
                  ) : null}

                  {trace.llm_prompt ? (
                    <TraceCodeBlock
                      title="Sanitized prompt"
                      content={trace.llm_prompt}
                    />
                  ) : null}
                </div>
              </details>
            ) : null}
          </div>
        ) : (
          <p className="mt-4 text-sm leading-6 text-stone-600">
            No backend debug trace was returned. Enable <code>DEBUG_TRACE_ENABLED=true</code> on
            the backend to show Gemini and rule-engine internals here.
          </p>
        )}
      </details>
    </section>
  );
}

function TraceField({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "warning";
}): JSX.Element {
  return (
    <div
      className={`rounded-[18px] border px-4 py-3 ${
        tone === "warning"
          ? "border-amber-200 bg-amber-50"
          : "border-stone-200 bg-white"
      }`}
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-stone-500">
        {label}
      </p>
      <p className="mt-2 break-words text-sm font-semibold text-stone-900">{value}</p>
    </div>
  );
}

function TraceList({
  icon: Icon,
  title,
  items,
  emptyLabel,
}: {
  icon: typeof ShieldCheck;
  title: string;
  items: string[];
  emptyLabel: string;
}): JSX.Element {
  return (
    <div className="min-w-0 rounded-[18px] border border-stone-200 bg-white p-4">
      <div className="flex items-center gap-3">
        <Icon aria-hidden="true" className="h-4 w-4 text-amber-700" />
        <h5 className="min-w-0 break-words text-sm font-semibold text-stone-900">{title}</h5>
      </div>

      {items.length > 0 ? (
        <ul className="mt-3 space-y-2">
          {items.map((item) => (
            <li
              key={`${title}-${item}`}
              className="break-words rounded-2xl bg-stone-50 px-3 py-2 text-sm leading-6 text-stone-700"
            >
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-stone-500">{emptyLabel}</p>
      )}
    </div>
  );
}

function TraceCodeBlock({
  title,
  content,
}: {
  title: string;
  content: string;
}): JSX.Element {
  return (
    <div className="min-w-0">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
        {title}
      </p>
      <pre className="mt-2 max-w-full overflow-x-auto rounded-[18px] bg-stone-950 p-4 text-xs leading-6 text-stone-100">
        <code>{content}</code>
      </pre>
    </div>
  );
}

function getLlmAssistLabel(trace?: DebugTrace | null): string {
  if (!trace) {
    return "LLM assisted: unavailable";
  }
  if (trace.gemini_used) {
    return "LLM assisted: Yes";
  }
  return "LLM assisted: No - rule-based fallback";
}

function toYesNo(value: boolean): string {
  return value ? "Yes" : "No";
}

function formatPurposeList(values: string[]): string {
  return values.map(formatPurpose).join(", ");
}

function formatPurpose(value: string): string {
  switch (value) {
    case "task_intent_detection":
      return "Task intent detection";
    case "followup_planning":
      return "Follow-up planning";
    case "explanation_assistance":
      return "Explanation assistance";
    default:
      return value.replace(/_/g, " ");
  }
}
