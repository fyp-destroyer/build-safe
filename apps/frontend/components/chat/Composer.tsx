"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { IconPaperclip, IconSend, IconMic } from "@/lib/icons";

// ⚠️ This exact two-layer wrapper structure (outer unconstrained wrapper with
// padding + overflow-y-hidden/scrollbar-gutter, inner mx-auto max-w box with
// no horizontal padding of its own) is required to line up pixel-for-pixel
// with the message thread above it — see design.md §10.4 for the two bugs
// this shape prevents. Do not "simplify" it to a single div.
export function Composer({
  onSend,
  disabled,
  autoFocus,
}: {
  onSend: (text: string) => void;
  disabled?: boolean;
  autoFocus?: boolean;
}) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [value]);

  useEffect(() => {
    if (autoFocus) ref.current?.focus();
  }, [autoFocus]);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  const hasInput = value.trim().length > 0;

  return (
    <div className="w-full overflow-y-hidden px-4 pb-4 [scrollbar-gutter:stable]">
      <div className="mx-auto max-w-[680px] rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-sm transition-colors focus-within:border-[var(--color-accent)]/50">
        <textarea
          ref={ref}
          rows={1}
          value={value}
          disabled={disabled}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder="Message CanIDIY…"
          className="max-h-[160px] w-full resize-none overflow-y-auto bg-transparent px-4 pt-3.5 pb-1 text-[15px] leading-relaxed outline-none placeholder:text-[var(--color-text-secondary)] disabled:opacity-50"
        />
        <div className="flex items-center justify-between px-2 pb-2 pt-1">
          <button
            type="button"
            aria-label="Attach photo"
            className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-full text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-inset)]"
          >
            <IconPaperclip width={17} height={17} />
          </button>
          <div className="flex items-center gap-1">
            <button
              type="button"
              aria-label="Voice input"
              className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-full text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-inset)]"
            >
              <IconMic width={16} height={16} />
            </button>
            <motion.button
              type="button"
              aria-label="Send message"
              onClick={submit}
              disabled={!hasInput || disabled}
              initial={false}
              animate={{ scale: hasInput ? 1 : 0.85, opacity: hasInput ? 1 : 0.4 }}
              transition={{ duration: 0.15, ease: "easeOut" }}
              className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-full bg-[var(--color-accent)] text-white transition-colors hover:bg-[var(--color-accent-hover)] disabled:cursor-not-allowed"
            >
              <IconSend width={14} height={14} />
            </motion.button>
          </div>
        </div>
      </div>
    </div>
  );
}
