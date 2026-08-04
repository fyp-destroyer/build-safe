"use client";

import { motion, useReducedMotion } from "motion/react";
import type { RiskCardData } from "@/lib/chatData";
import { RiskChip } from "@/components/risk/RiskChip";
import {
  IconAlertCircle,
  IconWrench,
  IconDollarSign,
  IconClock,
  IconCheck,
  IconBuilding,
  IconDownload,
} from "@/lib/icons";

// The single highest-information-density moment in the product — gets the
// app's one deliberate motion flourish (a scan-sweep on reveal) that nothing
// else gets, per the "spend boldness in one place" principle (design.md §1/§12).
export function RiskCard({ data }: { data: RiskCardData }) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      initial={{ opacity: 0, y: 12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="relative mt-2 w-full max-w-[560px] overflow-hidden rounded-xl border border-[var(--color-accent)]/25 bg-[var(--color-surface)] p-4 sm:p-6"
    >
      {!reduceMotion && (
        <motion.div
          aria-hidden
          initial={{ top: "-15%", opacity: 0 }}
          animate={{ top: "115%", opacity: [0, 1, 1, 0] }}
          transition={{ duration: 0.8, delay: 0.2, ease: "easeInOut" }}
          className="pointer-events-none absolute inset-x-0 h-14 bg-gradient-to-b from-transparent via-[var(--color-accent)]/20 to-transparent"
        />
      )}

      <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]">
        Risk Assessment
      </div>
      <h3 className="mb-4 text-lg font-semibold">{data.taskTitle}</h3>

      <RiskChip level={data.level} size="xl" />

      <p className="mt-4 text-base">{data.summary}</p>

      <hr className="my-5 border-[var(--color-border)]" />

      <h4 className="mb-3 text-sm font-semibold">Why this rating</h4>
      <ul className="mb-1 flex flex-col gap-2.5">
        {data.factors.map((factor) => (
          <li key={factor} className="flex items-start gap-2.5 text-sm">
            <IconAlertCircle width={16} height={16} className="mt-0.5 shrink-0 text-[var(--color-text-secondary)]" />
            <span>{factor}</span>
          </li>
        ))}
      </ul>

      <hr className="my-5 border-[var(--color-border)]" />

      {data.toolsWithheld ? (
        <div className="mb-5 flex gap-3 rounded-lg border border-[var(--risk-5)]/30 bg-[var(--risk-5)]/8 p-4 text-sm">
          <IconAlertCircle width={18} height={18} className="mt-0.5 shrink-0 text-[var(--risk-5)]" />
          <div>
            <div className="mb-1 font-semibold">DIY tool guidance withheld</div>
            <div className="text-[var(--color-text-secondary)]">{data.toolsWithheld}</div>
          </div>
        </div>
      ) : (
        <div className="mb-5 grid grid-cols-2 gap-4">
          {data.requiredTools && (
            <div>
              <div className="mb-2 text-xs font-semibold text-[var(--color-text-secondary)]">Required</div>
              <div className="flex flex-col gap-1.5">
                {data.requiredTools.map((t) => (
                  <span key={t} className="flex items-center gap-1.5 rounded-md border border-[var(--color-border)] px-2.5 py-1 text-xs">
                    <IconWrench width={12} height={12} /> {t}
                  </span>
                ))}
              </div>
            </div>
          )}
          {data.optionalTools && (
            <div>
              <div className="mb-2 text-xs font-semibold text-[var(--color-text-secondary)]">Optional</div>
              <div className="flex flex-col gap-1.5">
                {data.optionalTools.map((t) => (
                  <span key={t} className="flex items-center gap-1.5 rounded-md border border-[var(--color-border)] px-2.5 py-1 text-xs">
                    <IconWrench width={12} height={12} /> {t}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="mb-5 grid grid-cols-2 gap-3">
        <div className="flex items-center gap-2.5 rounded-lg bg-[var(--color-bg-inset)] p-3">
          <IconDollarSign width={16} height={16} className="text-[var(--color-accent)]" />
          <div>
            <div className="text-[11px] text-[var(--color-text-secondary)]">Estimated cost</div>
            <div className="text-sm font-semibold">{data.cost}</div>
          </div>
        </div>
        <div className="flex items-center gap-2.5 rounded-lg bg-[var(--color-bg-inset)] p-3">
          <IconClock width={16} height={16} className="text-[var(--color-accent)]" />
          <div>
            <div className="text-[11px] text-[var(--color-text-secondary)]">Estimated time</div>
            <div className="text-sm font-semibold">{data.time}</div>
          </div>
        </div>
      </div>

      {data.nextStep.kind === "checklist" ? (
        <div className="rounded-lg bg-[var(--color-bg-inset)] p-4">
          <div className="mb-3 text-sm font-semibold">Next steps — DIY checklist</div>
          <div className="flex flex-col gap-2.5">
            {data.nextStep.items.map((item) => (
              <div key={item} className="flex items-center gap-2.5 text-sm">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md border border-[var(--color-border)] text-[var(--color-text-secondary)]">
                  <IconCheck width={12} height={12} />
                </span>
                {item}
              </div>
            ))}
          </div>
          <button
            type="button"
            className="mt-4 flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--color-accent)]/40 px-3 py-1.5 text-xs font-semibold text-[var(--color-accent)] transition-colors hover:bg-[var(--color-accent)]/10"
          >
            <IconDownload width={13} height={13} /> Download report
          </button>
        </div>
      ) : (
        <div className="rounded-lg bg-[var(--color-bg-inset)] p-4">
          <div className="mb-2 flex items-center gap-2">
            <IconBuilding width={16} height={16} className="text-[var(--color-accent)]" />
            <span className="text-sm font-semibold">Recommended: {data.nextStep.category}</span>
          </div>
          <p className="text-sm text-[var(--color-text-secondary)]">{data.nextStep.blurb}</p>
        </div>
      )}
    </motion.div>
  );
}
