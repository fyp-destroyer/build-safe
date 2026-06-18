import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

interface TypingIndicatorProps {
  messages: string[];
}

export function TypingIndicator({ messages }: TypingIndicatorProps): JSX.Element {
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    setActiveIndex(0);
  }, [messages]);

  useEffect(() => {
    if (messages.length <= 1) {
      return;
    }

    const interval = window.setInterval(() => {
      setActiveIndex((current) => (current + 1) % messages.length);
    }, 1400);

    return () => window.clearInterval(interval);
  }, [messages]);

  const activeMessage = messages[activeIndex] ?? "Assessing safety conditions...";

  return (
    <div className="flex min-w-0 justify-start">
      <div className="flex w-full max-w-full gap-2 sm:max-w-[88%] sm:gap-3">
        <div className="mt-1 hidden h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-amber-100 text-amber-900 sm:flex">
          <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin" />
        </div>

        <div className="min-w-0 flex-1">
          <span className="mb-1 block text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
            BuildSafe AI
          </span>
          <div className="rounded-[20px] border border-stone-200 bg-white px-3 py-3 text-sm text-stone-700 shadow-sm sm:rounded-[24px] sm:px-5 sm:py-4">
            <div className="flex items-center gap-3">
              <span className="min-w-0 flex-1 break-words">{activeMessage}</span>
              <span className="flex items-center gap-1" aria-hidden="true">
                <span className="h-2 w-2 animate-bounce rounded-full bg-amber-500 [animation-delay:-0.3s]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-amber-500 [animation-delay:-0.15s]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-amber-500" />
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
