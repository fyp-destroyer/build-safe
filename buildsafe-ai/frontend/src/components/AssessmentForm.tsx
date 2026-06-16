import { ClipboardCheck, Hammer, Loader2 } from "lucide-react";
import { FormEvent, useState } from "react";

import type { AssessmentRequest, LocationType, SkillLevel, Urgency } from "../types/assessment";

interface AssessmentFormProps {
  isSubmitting: boolean;
  onSubmit: (payload: AssessmentRequest) => void;
}

const skillOptions: SkillLevel[] = ["beginner", "intermediate", "expert"];
const locationOptions: LocationType[] = ["house", "apartment", "shop", "office"];
const urgencyOptions: Urgency[] = ["low", "medium", "high", "emergency"];

export function AssessmentForm({ isSubmitting, onSubmit }: AssessmentFormProps): JSX.Element {
  const [taskDescription, setTaskDescription] = useState("install a ceiling fan");
  const [skillLevel, setSkillLevel] = useState<SkillLevel>("beginner");
  const [availableTools, setAvailableTools] = useState("drill, ladder");
  const [locationType, setLocationType] = useState<LocationType>("house");
  const [urgency, setUrgency] = useState<Urgency>("medium");
  const [budgetRange, setBudgetRange] = useState("$50-$100");
  const [validationError, setValidationError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();

    const task = taskDescription.trim();
    const budget = budgetRange.trim();
    const tools = availableTools
      .split(",")
      .map((tool) => tool.trim())
      .filter(Boolean);

    if (task.length < 3) {
      setValidationError("Enter a task with at least 3 characters.");
      return;
    }

    if (task.length > 300) {
      setValidationError("Keep the task description under 300 characters.");
      return;
    }

    if (tools.length > 25) {
      setValidationError("List at most 25 available tools.");
      return;
    }

    setValidationError(null);
    onSubmit({
      task_description: task,
      user_skill_level: skillLevel,
      available_tools: tools,
      location_type: locationType,
      urgency,
      budget_range: budget || "not specified",
      answers_to_followups: {},
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <label htmlFor="task-description" className="text-sm font-semibold text-zinc-800">
          Task description
        </label>
        <textarea
          id="task-description"
          value={taskDescription}
          onChange={(event) => setTaskDescription(event.target.value)}
          required
          rows={4}
          className="mt-2 w-full resize-y rounded-md border border-zinc-300 bg-white px-3 py-3 text-sm text-zinc-900 shadow-sm outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <FieldSelect
          label="Skill level"
          value={skillLevel}
          options={skillOptions}
          onChange={(value) => setSkillLevel(value as SkillLevel)}
        />
        <FieldSelect
          label="Location type"
          value={locationType}
          options={locationOptions}
          onChange={(value) => setLocationType(value as LocationType)}
        />
      </div>

      <div>
        <label htmlFor="available-tools" className="flex items-center gap-2 text-sm font-semibold text-zinc-800">
          <Hammer aria-hidden="true" className="h-4 w-4 text-zinc-500" />
          Available tools
        </label>
        <input
          id="available-tools"
          value={availableTools}
          onChange={(event) => setAvailableTools(event.target.value)}
          className="mt-2 w-full rounded-md border border-zinc-300 bg-white px-3 py-2.5 text-sm text-zinc-900 shadow-sm outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <FieldSelect
          label="Urgency"
          value={urgency}
          options={urgencyOptions}
          onChange={(value) => setUrgency(value as Urgency)}
        />
        <div>
          <label htmlFor="budget-range" className="text-sm font-semibold text-zinc-800">
            Budget range
          </label>
          <input
            id="budget-range"
            value={budgetRange}
            onChange={(event) => setBudgetRange(event.target.value)}
            className="mt-2 w-full rounded-md border border-zinc-300 bg-white px-3 py-2.5 text-sm text-zinc-900 shadow-sm outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
          />
        </div>
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-zinc-900 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-zinc-800 focus:outline-none focus:ring-2 focus:ring-amber-300 disabled:cursor-not-allowed disabled:opacity-70"
      >
        {isSubmitting ? (
          <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
        ) : (
          <ClipboardCheck aria-hidden="true" className="h-4 w-4" />
        )}
        Assess Risk
      </button>

      {validationError ? (
        <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {validationError}
        </p>
      ) : null}
    </form>
  );
}

interface FieldSelectProps {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}

function FieldSelect({ label, value, options, onChange }: FieldSelectProps): JSX.Element {
  const fieldId = label.toLowerCase().replace(/\s+/g, "-");

  return (
    <div>
      <label htmlFor={fieldId} className="text-sm font-semibold text-zinc-800">
        {label}
      </label>
      <select
        id={fieldId}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full rounded-md border border-zinc-300 bg-white px-3 py-2.5 text-sm capitalize text-zinc-900 shadow-sm outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  );
}
