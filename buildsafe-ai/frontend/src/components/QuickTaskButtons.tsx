import { Sparkles } from "lucide-react";

interface QuickTaskButtonsProps {
  tasks: string[];
  onSelect: (task: string) => void;
  disabled?: boolean;
}

export function QuickTaskButtons({
  tasks,
  onSelect,
  disabled = false,
}: QuickTaskButtonsProps): JSX.Element {
  return (
    <div className="rounded-[28px] border border-amber-200 bg-amber-50/80 p-4">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-white text-amber-800 shadow-sm">
          <Sparkles aria-hidden="true" className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-stone-900">Quick starts</p>
          <p className="mt-1 text-sm leading-6 text-stone-600">
            Use a sample supervisor-demo prompt or type your own task below.
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {tasks.map((task) => (
          <button
            key={task}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(task)}
            className="rounded-full border border-amber-300 bg-white px-4 py-2 text-sm font-semibold text-amber-900 transition hover:border-amber-400 hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {task}
          </button>
        ))}
      </div>
    </div>
  );
}
