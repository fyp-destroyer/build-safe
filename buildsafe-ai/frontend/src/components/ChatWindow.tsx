import type { ReactNode, RefObject } from "react";

interface ChatWindowProps {
  children: ReactNode;
  footer: ReactNode;
  scrollRef: RefObject<HTMLDivElement>;
}

export function ChatWindow({
  children,
  footer,
  scrollRef,
}: ChatWindowProps): JSX.Element {
  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-[32px] border border-white/70 bg-white/85 shadow-[0_28px_80px_rgba(66,44,16,0.12)] backdrop-blur">
      <header className="shrink-0 border-b border-stone-200/80 bg-gradient-to-r from-stone-950 via-stone-900 to-stone-800 px-5 py-5 text-white sm:px-7">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-300">
              Guided Safety Consultation
            </p>
            <h2 className="display-font mt-2 text-3xl leading-tight">
              Chat-based task assessment
            </h2>
          </div>

          <div className="flex flex-wrap gap-2 text-xs font-semibold text-stone-100">
            <span className="rounded-full border border-white/20 bg-white/10 px-3 py-1.5">
              Conversational intake
            </span>
            <span className="rounded-full border border-white/20 bg-white/10 px-3 py-1.5">
              Safety-first output
            </span>
            <span className="rounded-full border border-white/20 bg-white/10 px-3 py-1.5">
              Existing backend preserved
            </span>
          </div>
        </div>
      </header>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto bg-[linear-gradient(180deg,rgba(255,250,241,0.92),rgba(255,255,255,0.96))] px-4 py-5 sm:px-6 sm:py-6"
      >
        {children}
      </div>

      <div className="shrink-0 border-t border-stone-200/80 bg-white/90 px-4 py-4 sm:px-6">
        {footer}
      </div>
    </section>
  );
}
