import { SendHorizontal } from "lucide-react";
import { FormEvent, KeyboardEvent } from "react";

interface OptionButton {
  label: string;
  value: string;
}

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled: boolean;
  placeholder: string;
  rows: number;
  options?: OptionButton[];
  onSelectOption: (value: string) => void;
  error?: string | null;
}

export function ChatInput({
  value,
  onChange,
  onSubmit,
  disabled,
  placeholder,
  rows,
  options = [],
  onSelectOption,
  error,
}: ChatInputProps): JSX.Element {
  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onSubmit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  }

  return (
    <div className="space-y-3">
      {options.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              disabled={disabled}
              onClick={() => onSelectOption(option.value)}
              className="rounded-full border border-stone-300 bg-stone-50 px-4 py-2 text-sm font-semibold text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {option.label}
            </button>
          ))}
        </div>
      ) : null}

      <form onSubmit={handleSubmit} className="rounded-[28px] border border-stone-200 bg-stone-50 p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.5)]">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="min-w-0 flex-1">
            {rows > 1 ? (
              <textarea
                value={value}
                onChange={(event) => onChange(event.target.value)}
                onKeyDown={handleKeyDown}
                rows={rows}
                disabled={disabled}
                placeholder={placeholder}
                className="min-h-[52px] w-full max-h-36 resize-none overflow-y-auto rounded-2xl border border-stone-200 bg-white px-4 py-3 text-sm text-stone-900 outline-none transition focus:border-amber-400 focus:ring-4 focus:ring-amber-100 disabled:cursor-not-allowed disabled:bg-stone-100"
              />
            ) : (
              <input
                value={value}
                onChange={(event) => onChange(event.target.value)}
                disabled={disabled}
                placeholder={placeholder}
                className="w-full rounded-2xl border border-stone-200 bg-white px-4 py-3 text-sm text-stone-900 outline-none transition focus:border-amber-400 focus:ring-4 focus:ring-amber-100 disabled:cursor-not-allowed disabled:bg-stone-100"
              />
            )}
          </div>

          <button
            type="submit"
            disabled={disabled}
            className="inline-flex h-12 items-center justify-center gap-2 rounded-2xl bg-stone-950 px-5 text-sm font-semibold text-white transition hover:bg-stone-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <SendHorizontal aria-hidden="true" className="h-4 w-4" />
            Send
          </button>
        </div>

        {error ? (
          <p className="mt-3 rounded-2xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {error}
          </p>
        ) : null}
      </form>
    </div>
  );
}
