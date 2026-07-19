"use client";

import { motion } from "motion/react";

export function QuickReplyChips({
  options,
  onSelect,
  disabled,
}: {
  options: string[];
  onSelect: (option: string) => void;
  disabled?: boolean;
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
          className="cursor-pointer rounded-full border border-[var(--color-border)] bg-[var(--color-bg)] px-3.5 py-1.5 text-sm font-medium text-[var(--color-text-primary)] transition-colors hover:border-[var(--color-accent)] disabled:cursor-not-allowed disabled:opacity-40"
        >
          {option}
        </motion.button>
      ))}
    </div>
  );
}
