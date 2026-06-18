import { HardHat, UserRound } from "lucide-react";
import type { ReactNode } from "react";

interface ChatMessageProps {
  children: ReactNode;
  role: "assistant" | "user";
  tone?: "default" | "highlight" | "warning";
}

const toneClasses = {
  assistant: {
    default: "border-stone-200 bg-white text-stone-800",
    highlight: "border-amber-200 bg-amber-50 text-stone-900",
    warning: "border-red-200 bg-red-50 text-red-900",
  },
  user: {
    default: "border-stone-900 bg-stone-900 text-white",
    highlight: "border-stone-900 bg-stone-900 text-white",
    warning: "border-stone-900 bg-stone-900 text-white",
  },
} as const;

export function ChatMessage({
  children,
  role,
  tone = "default",
}: ChatMessageProps): JSX.Element {
  const isAssistant = role === "assistant";
  const containerClass = isAssistant ? "justify-start" : "justify-end";
  const bubbleClass = toneClasses[role][tone];

  return (
    <div className={`flex min-w-0 ${containerClass}`}>
      <div
        className={`flex w-full max-w-full gap-2 sm:max-w-[88%] sm:gap-3 ${isAssistant ? "" : "flex-row-reverse"}`}
      >
        <div
          className={`mt-1 hidden h-10 w-10 shrink-0 items-center justify-center rounded-2xl sm:flex ${
            isAssistant ? "bg-amber-100 text-amber-900" : "bg-stone-200 text-stone-900"
          }`}
        >
          {isAssistant ? (
            <HardHat aria-hidden="true" className="h-5 w-5" />
          ) : (
            <UserRound aria-hidden="true" className="h-5 w-5" />
          )}
        </div>

        <div className={`flex min-w-0 flex-1 flex-col ${isAssistant ? "" : "items-end"}`}>
          <span className="mb-1 text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
            {isAssistant ? "BuildSafe AI" : "You"}
          </span>

          <div
            className={`max-w-full overflow-hidden rounded-[20px] border px-3 py-3 shadow-sm sm:rounded-[24px] sm:px-5 sm:py-4 ${bubbleClass}`}
          >
            <div className="min-w-0 break-words whitespace-pre-line text-sm leading-7 sm:text-[15px]">
              {children}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
