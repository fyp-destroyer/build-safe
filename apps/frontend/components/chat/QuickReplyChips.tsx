"use client";

import { motion } from "motion/react";

export function QuickReplyChips({
  options,
  onSelect,
  disabled,
  highlight,
}: {
  options: string[];
  onSelect: (option: string) => void;
  disabled?: boolean;
  /**
   * Option to render as pre-selected, used when the backend read an answer out
   * of the user's own description.
   *
   * Emphasis only — the chip still has to be tapped, and the other options are
   * styled and sized identically so the suggestion reads as a default rather
   * than a recommendation. On a safety question, making the alternatives look
   * discouraged would be the wrong nudge.
   */
  highlight?: string | null;
}) {
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {options.map((option, i) => (
        <motion.button
          key={option}
          type="button"
          disabled={disabled}
          onClick={() => onSelect(option)}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.04, duration: 0.18 }}
          whileHover={disabled ? undefined : { scale: 1.03 }}
          whileTap={disabled ? undefined : { scale: 0.97 }}
          className={
            "cursor-pointer rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 " +
            (option === highlight
              ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-text-primary)]"
              : "border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text-primary)] hover:border-[var(--color-accent)]")
          }
        >
          {option}
        </motion.button>
      ))}
    </div>
  );
}
