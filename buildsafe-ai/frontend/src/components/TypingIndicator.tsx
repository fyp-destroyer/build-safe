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
    <div className="flex justify-start">
      <div className="flex max-w-[88%] gap-3">
        <div className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-amber-100 text-amber-900">
          <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin" />
        </div>

        <div className="min-w-0">
          <span className="mb-1 block text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
            BuildSafe AI
          </span>
          <div className="rounded-[24px] border border-stone-200 bg-white px-5 py-4 text-sm text-stone-700 shadow-sm">
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
