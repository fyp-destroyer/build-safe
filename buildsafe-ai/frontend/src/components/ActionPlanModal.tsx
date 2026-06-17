import {
  BriefcaseBusiness,
  CheckCircle2,
  ClipboardCheck,
  HardHat,
  Info,
  ListChecks,
  Package,
  ScrollText,
  ShieldAlert,
  ShieldCheck,
  TriangleAlert,
  Wrench,
  X,
  type LucideIcon,
} from "lucide-react";
import { useEffect, type ReactNode } from "react";

import type { ActionPlanResponse, PlanType } from "../types/assessment";

interface ActionPlanModalProps {
  plan: ActionPlanResponse;
  onClose: () => void;
}

const planTypeStyles: Record<
  PlanType,
  {
    label: string;
    icon: LucideIcon;
    badge: string;
    iconPanel: string;
    notice: string;
  }
> = {
  safe_diy_plan: {
    label: "Safe DIY plan",
    icon: CheckCircle2,
    badge: "border-emerald-300 bg-emerald-50 text-emerald-900",
    iconPanel: "bg-emerald-100 text-emerald-800",
    notice: "border-emerald-200 bg-emerald-50 text-emerald-950",
  },
  supervised_plan: {
    label: "Supervised plan",
    icon: ShieldCheck,
    badge: "border-sky-300 bg-sky-50 text-sky-900",
    iconPanel: "bg-sky-100 text-sky-800",
    notice: "border-sky-200 bg-sky-50 text-sky-950",
  },
  preparation_checklist: {
    label: "Preparation checklist",
    icon: ClipboardCheck,
    badge: "border-amber-300 bg-amber-50 text-amber-900",
    iconPanel: "bg-amber-100 text-amber-900",
    notice: "border-amber-200 bg-amber-50 text-amber-950",
  },
  professional_only_checklist: {
    label: "Professional-only checklist",
    icon: ShieldAlert,
    badge: "border-red-400 bg-red-100 text-red-950",
    iconPanel: "bg-red-100 text-red-900",
    notice: "border-red-200 bg-red-50 text-red-950",
  },
};

export function ActionPlanModal({
  plan,
  onClose,
}: ActionPlanModalProps): JSX.Element {
  const style = planTypeStyles[plan.plan_type];
  const Icon = style.icon;

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 bg-stone-950/55 p-4 backdrop-blur-sm sm:p-6"
      onClick={onClose}
      role="presentation"
    >
      <div className="flex h-full items-start justify-center">
        <div
          className="flex max-h-full w-full max-w-5xl flex-col overflow-hidden rounded-[32px] border border-stone-200 bg-[linear-gradient(180deg,#fffdf9_0%,#ffffff_28%,#f4efe6_100%)] shadow-[0_36px_120px_rgba(28,25,23,0.34)]"
          onClick={(event) => event.stopPropagation()}
          role="dialog"
          aria-modal="true"
          aria-labelledby="action-plan-title"
        >
          <div className="hazard-stripe h-2 w-full" />

          <header className="shrink-0 border-b border-stone-200 bg-white/90 px-5 py-5 sm:px-7">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-3">
                  <span
                    className={`inline-flex items-center gap-2 rounded-full border px-3.5 py-2 text-sm font-semibold ${style.badge}`}
                  >
                    <Icon aria-hidden="true" className="h-4 w-4" />
                    {style.label}
                  </span>
                  <span className="rounded-full border border-stone-200 bg-stone-50 px-3.5 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-stone-600">
                    {plan.allowed_to_show_steps ? "Steps allowed" : "Checklist only"}
                  </span>
                </div>

                <h2
                  id="action-plan-title"
                  className="display-font mt-4 text-3xl leading-tight text-stone-950"
                >
                  {plan.title}
                </h2>
                <p className="mt-3 max-w-3xl text-sm leading-7 text-stone-600">
                  {plan.summary}
                </p>
              </div>

              <button
                type="button"
                onClick={onClose}
                className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-stone-200 bg-stone-50 text-stone-700 transition hover:border-stone-300 hover:bg-stone-100"
                aria-label="Close action plan"
              >
                <X aria-hidden="true" className="h-5 w-5" />
              </button>
            </div>

            <div className={`mt-5 rounded-[24px] border px-4 py-3 ${style.notice}`}>
              <div className="flex gap-3">
                <TriangleAlert aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0" />
                <p className="text-sm font-semibold leading-6">{plan.safety_notice}</p>
              </div>
            </div>
          </header>

          <div className="flex-1 overflow-y-auto px-5 py-5 sm:px-7 sm:py-6">
            <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
              <SectionCard icon={ListChecks} title="Before You Start" iconClassName={style.iconPanel}>
                <ListBlock
                  items={plan.prerequisites}
                  emptyLabel="No prerequisites were returned."
                />
              </SectionCard>

              <SectionCard icon={Wrench} title="Tools, Materials, and PPE" iconClassName={style.iconPanel}>
                <div className="grid gap-3 md:grid-cols-3">
                  <ChipGroup icon={Wrench} title="Tools" items={plan.tools_required} />
                  <ChipGroup icon={Package} title="Materials" items={plan.materials_required} />
                  <ChipGroup icon={HardHat} title="PPE" items={plan.ppe_required} />
                </div>
              </SectionCard>
            </div>

            <SectionCard
              icon={ClipboardCheck}
              title={plan.allowed_to_show_steps ? "Safe Plan" : "Checklist"}
              iconClassName={style.iconPanel}
              className="mt-4"
            >
              <StepList
                steps={plan.steps}
                prefix={plan.allowed_to_show_steps ? "Step" : "Item"}
              />
            </SectionCard>

            <div className="mt-4 grid gap-4 xl:grid-cols-2">
              <SectionCard icon={ShieldAlert} title="Stop Immediately If" iconClassName="bg-red-100 text-red-900">
                <ListBlock
                  items={plan.stop_conditions}
                  emptyLabel="No stop conditions were returned."
                  tone="danger"
                />
              </SectionCard>

              <SectionCard icon={BriefcaseBusiness} title="Professional Help" iconClassName={style.iconPanel}>
                <ListBlock
                  title="When to call"
                  items={plan.when_to_call_professional}
                  emptyLabel="No professional escalation notes were returned."
                />
                <ListBlock
                  title="Questions to ask"
                  items={plan.professional_questions}
                  emptyLabel="No professional questions were returned."
                  className="mt-4"
                />
              </SectionCard>
            </div>

            <SectionCard icon={ScrollText} title="Disclaimer" iconClassName="bg-stone-100 text-stone-700" className="mt-4">
              <p className="text-sm leading-7 text-stone-700">{plan.disclaimer}</p>
            </SectionCard>

            {plan.debug_trace ? (
              <SectionCard icon={Info} title="Developer Trace" iconClassName="bg-stone-100 text-stone-700" className="mt-4">
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <TraceTile label="Generated" value={String(plan.debug_trace.action_plan_generated)} />
                  <TraceTile label="Plan type" value={plan.debug_trace.plan_type} />
                  <TraceTile label="LLM used" value={String(plan.debug_trace.llm_used_for_plan)} />
                  <TraceTile
                    label="Restriction"
                    value={String(plan.debug_trace.safety_restriction_applied)}
                  />
                </div>
                {plan.debug_trace.reason_if_steps_blocked ? (
                  <p className="mt-4 rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3 text-sm leading-6 text-stone-700">
                    {plan.debug_trace.reason_if_steps_blocked}
                  </p>
                ) : null}
              </SectionCard>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

function SectionCard({
  icon: Icon,
  title,
  children,
  iconClassName,
  className = "",
}: {
  icon: LucideIcon;
  title: string;
  children: ReactNode;
  iconClassName: string;
  className?: string;
}): JSX.Element {
  return (
    <section className={`rounded-[26px] border border-stone-200 bg-white p-5 shadow-sm ${className}`}>
      <div className="flex items-center gap-3">
        <div className={`flex h-10 w-10 items-center justify-center rounded-2xl ${iconClassName}`}>
          <Icon aria-hidden="true" className="h-5 w-5" />
        </div>
        <h3 className="text-lg font-bold text-stone-950">{title}</h3>
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function ChipGroup({
  icon: Icon,
  title,
  items,
}: {
  icon: LucideIcon;
  title: string;
  items: string[];
}): JSX.Element {
  return (
    <div className="rounded-[22px] border border-stone-200 bg-stone-50 p-4">
      <div className="flex items-center gap-2">
        <Icon aria-hidden="true" className="h-4 w-4 text-amber-800" />
        <h4 className="text-sm font-bold text-stone-950">{title}</h4>
      </div>

      {items.length > 0 ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {items.map((item) => (
            <span
              key={`${title}-${item}`}
              className="rounded-full border border-stone-200 bg-white px-3 py-2 text-sm leading-5 text-stone-700"
            >
              {item}
            </span>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-stone-500">None listed.</p>
      )}
    </div>
  );
}

function StepList({
  steps,
  prefix,
}: {
  steps: ActionPlanResponse["steps"];
  prefix: "Step" | "Item";
}): JSX.Element {
  if (steps.length === 0) {
    return <p className="text-sm text-stone-500">No checklist items were returned.</p>;
  }

  return (
    <ol className="space-y-3">
      {steps.map((step) => (
        <li
          key={`${prefix}-${step.step_number}-${step.title}`}
          className="rounded-[22px] border border-stone-200 bg-stone-50 p-4"
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
                {prefix} {step.step_number}
              </p>
              <h4 className="mt-2 text-base font-bold text-stone-950">{step.title}</h4>
            </div>
            <span className="inline-flex shrink-0 rounded-full border border-stone-200 bg-white px-3 py-1.5 text-xs font-semibold text-stone-600">
              {step.estimated_time}
            </span>
          </div>
          <p className="mt-3 text-sm leading-7 text-stone-700">{step.description}</p>
          {step.safety_note ? (
            <p className="mt-3 rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-semibold leading-6 text-amber-950">
              {step.safety_note}
            </p>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

function ListBlock({
  title,
  items,
  emptyLabel,
  tone = "default",
  className = "",
}: {
  title?: string;
  items: string[];
  emptyLabel: string;
  tone?: "default" | "danger";
  className?: string;
}): JSX.Element {
  return (
    <div className={className}>
      {title ? (
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
          {title}
        </p>
      ) : null}

      {items.length > 0 ? (
        <ul className={title ? "mt-3 space-y-2" : "space-y-2"}>
          {items.map((item) => (
            <li
              key={`${title ?? "item"}-${item}`}
              className={`rounded-2xl px-3 py-2 text-sm leading-6 ${
                tone === "danger"
                  ? "bg-red-50 text-red-900"
                  : "bg-stone-50 text-stone-700"
              }`}
            >
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className={title ? "mt-3 text-sm text-stone-500" : "text-sm text-stone-500"}>
          {emptyLabel}
        </p>
      )}
    </div>
  );
}

function TraceTile({
  label,
  value,
}: {
  label: string;
  value: string;
}): JSX.Element {
  return (
    <div className="rounded-[20px] border border-stone-200 bg-stone-50 p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
        {label}
      </p>
      <p className="mt-2 break-words text-sm font-semibold leading-6 text-stone-900">
        {value}
      </p>
    </div>
  );
}
