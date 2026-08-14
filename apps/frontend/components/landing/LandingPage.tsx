"use client";

/**
 * The homepage, built as CanIDIY's own case register.
 *
 * WHY IT LOOKS LIKE A BOUND REGISTER AND NOT A SAAS LANDING PAGE
 * --------------------------------------------------------------
 * design.md §1 fixes the product's framing as an *inspection log*, not a
 * messaging app: monospace metadata, entries filed by trade, a verdict that
 * reads as a completed report. The marketing surface inherits that framing
 * rather than inventing a second identity for the front door. So the page is
 * structured as the register itself — a key, a set of filed case entries, the
 * standing clauses that govern them, and a scope note — instead of the usual
 * hero-plus-three-feature-cards arrangement. The proof is the entries; there is
 * nothing here that claims a capability the entries do not demonstrate.
 *
 * WHY IT IS ALWAYS DARK
 * ---------------------
 * The root element carries `dark`, so the whole subtree resolves the `.dark`
 * token block in globals.css no matter what the user's theme choice is. That is
 * deliberate and it matches the existing precedent: the auth screen is
 * always-dark too (design.md §9), and this page leads directly into it. A
 * visitor going home → sign in should not watch the palette invert halfway.
 * Note this is done by *re-scoping the tokens*, not by hardcoding hex values —
 * every colour below still comes from the same custom properties the app uses,
 * so a token change propagates here as well.
 *
 * WHAT MAY NOT DRIFT
 * ------------------
 * Risk colour is always rendered through `RiskChip` (colour + icon + label
 * together, never colour alone) and the five levels keep their locked order.
 * Brand orange is used for the register's ink — rules, actions, the `max`
 * operator — and never to imply a risk level. Every number and rule id on this
 * page is real; see the header of `registerData.ts` for what is factual, what
 * is illustrative, and what must never be added.
 */

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { useUser } from "@clerk/nextjs";

import { RiskChip } from "@/components/risk/RiskChip";
import { RISK_LEVELS, type RiskLevel } from "@/lib/riskLevels";
import { IconChevronRight, IconSend } from "@/lib/icons";
import {
  CASES,
  CLAUSES,
  LEDGER_FACTS,
  OUT_OF_SCOPE,
  SCALE,
  type CaseEntry,
} from "./registerData";

/* Shared measurements. The register is ruled on one module: a fixed metadata
   rail on the left at desktop widths, the entry body on the right. Every
   horizontal hairline is the same 1px border token, so the page reads as one
   continuous sheet rather than a stack of separate cards. */
const SHELL = "mx-auto w-full max-w-[1140px] px-5 sm:px-8";
const RAIL =
  "font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--color-text-secondary)]";

/* ------------------------------------------------------------------ */
/* Verdict stamp — the page's one authored motion moment.              */
/* ------------------------------------------------------------------ */

/**
 * The verdict, rendered the way a stamp hits paper: it arrives over-scale and
 * off-angle, then settles. This is the only entrance animation on the page —
 * everything else is visible from first paint and only responds to interaction.
 *
 * The same verdict is also present as plain text in the entry's ledger row, so
 * nothing load-bearing depends on this rendering: if motion never runs, the
 * reader still has the level and its label.
 */
function VerdictStamp({ level }: { level: RiskLevel }) {
  const def = RISK_LEVELS[level];
  const reduced = useReducedMotion();

  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, scale: 1.34, rotate: -11, filter: "blur(7px)" }}
      whileInView={{ opacity: 1, scale: 1, rotate: -2.5, filter: "blur(0px)" }}
      viewport={{ once: true, amount: 0.6 }}
      transition={{ duration: 0.62, ease: [0.16, 1, 0.3, 1] }}
      className="flex w-full shrink-0 flex-col items-start gap-1 border-2 px-5 py-4 sm:w-[15.5rem]"
      style={{ borderColor: def.colorVar, background: `color-mix(in srgb, ${def.colorVar} 14%, transparent)` }}
    >
      <span
        className="font-mono text-[10px] uppercase tracking-[0.2em]"
        style={{ color: def.colorVar }}
      >
        Verdict
      </span>
      {/* Numeral above the label rather than beside it: at this width the two
          longest labels ("Dangerous / Do Not Attempt", "Professional
          Recommended") shred into one- and two-word slivers when they have to
          share the line with a 3rem numeral. */}
      <span
        className="text-[3rem] font-semibold leading-[1.05] tracking-[-0.03em] sm:text-[3.5rem]"
        style={{ color: def.colorVar }}
      >
        {level}
      </span>
      <span className="text-[15px] font-semibold leading-[1.2] text-[var(--color-text-primary)] sm:text-base">
        {def.label}
      </span>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* Header                                                             */
/* ------------------------------------------------------------------ */

/**
 * One action, not two. `proxy.ts` bounces a signed-out visitor from /chat to
 * /login with a redirect_url, so a separate "Sign in" link went to the same
 * screen as the primary button — two controls competing for one outcome. The
 * button is the survivor; returning users reach the same place by pressing it.
 *
 * That single href is also why no auth state is needed to render the action: it
 * is correct signed in or out, and works before Clerk has loaded (or if its
 * script never does). Session state only changes the button's *label*.
 */
function LandingHeader() {
  // `isLoaded` is false during SSR and on the first client render — Clerk
  // resolves the session asynchronously — so both agree on the signed-out
  // label and the swap happens after hydration rather than across it.
  const { isLoaded, isSignedIn } = useUser();
  const signedOut = !(isLoaded && isSignedIn);

  return (
    <header className="sticky top-0 z-50 border-b border-[var(--color-border)] bg-[var(--color-bg)]/95 backdrop-blur-[2px]">
      <div className={`${SHELL} flex h-[60px] items-center justify-between gap-4`}>
        <Link href="/" className="flex items-center gap-2.5" aria-label="CanIDIY home">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--color-accent)] text-sm font-bold text-white">
            C
          </span>
          <span className="text-sm font-semibold text-[var(--color-text-primary)]">CanIDIY</span>
        </Link>

        <nav className="flex items-center gap-1 sm:gap-2">
          <a
            href="#cases"
            className="hidden rounded-full px-3 py-2 text-sm text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text-primary)] sm:block"
          >
            Worked cases
          </a>
          <a
            href="#clauses"
            className="hidden rounded-full px-3 py-2 text-sm text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text-primary)] sm:block"
          >
            How a verdict is reached
          </a>
          <Link
            href="/chat"
            className="ml-1 inline-flex items-center gap-1.5 whitespace-nowrap rounded-full bg-[var(--color-accent)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--color-accent-hover)]"
          >
            {signedOut ? "Start an assessment" : "Open CanIDIY"}
            <IconChevronRight width={15} height={15} />
          </Link>
        </nav>
      </div>
    </header>
  );
}

/* ------------------------------------------------------------------ */
/* Register head — first viewport                                     */
/* ------------------------------------------------------------------ */

function RegisterHead() {
  return (
    <section className={`${SHELL} pb-16 pt-16 sm:pt-24`}>
      <h1 className="max-w-[14ch] text-[clamp(2.6rem,8vw,5.25rem)] font-semibold leading-[0.96] tracking-[-0.035em] text-[var(--color-text-primary)]">
        Should you be doing this yourself?
      </h1>

      <p className="mt-7 max-w-[62ch] text-[17px] leading-[1.65] text-[var(--color-text-secondary)] sm:text-lg">
        Describe the job in your own words. CanIDIY asks the questions that change the
        answer, then files one of five verdicts — with the exact rules that produced it.
        It is built to tell you no.
      </p>

      <div className="mt-9 flex flex-wrap items-center gap-3">
        <Link
          href="/chat"
          className="inline-flex items-center gap-2 rounded-full bg-[var(--color-accent)] px-6 py-3.5 text-[15px] font-semibold text-white transition-colors hover:bg-[var(--color-accent-hover)]"
        >
          Start an assessment
          <IconSend width={16} height={16} />
        </Link>
        <a
          href="#cases"
          className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border)] px-6 py-3.5 text-[15px] font-semibold text-[var(--color-text-primary)] transition-colors hover:border-[var(--color-text-secondary)]"
        >
          Read a filed case
        </a>
      </div>

      {/* The register's key. Rule counts are real: every hazard rule in the
          shipped catalog escalates to exactly one of these levels, and the
          distribution is itself the argument — most of the catalog pushes to
          "Professional Required" or worse. */}
      {/* Capped well inside the shell: at the full 1140px the count column ends
          up an inch of empty ground away from the sentence it belongs to, and
          reads as page furniture instead of as the row's data. */}
      <div className="mt-16 max-w-[58rem] sm:mt-20">
        <div className="flex items-baseline justify-between gap-4 border-b border-[var(--color-text-secondary)]/40 pb-3">
          <h2 className={RAIL}>The five verdicts</h2>
          <span className={RAIL}>Rules that reach it</span>
        </div>

        <ul>
          {SCALE.map((rung) => (
            <li
              key={rung.level}
              className="grid grid-cols-[2.25rem_1fr_auto] items-center gap-x-4 gap-y-2 border-b border-[var(--color-border)] py-4 sm:grid-cols-[2.75rem_minmax(0,17rem)_1fr_auto] sm:gap-x-6"
            >
              <span
                className="font-mono text-2xl leading-none sm:text-[28px]"
                style={{ color: RISK_LEVELS[rung.level].colorVar }}
              >
                {rung.level}
              </span>
              <span className="col-start-2">
                <RiskChip level={rung.level} size="sm" />
              </span>
              <span className="col-span-2 col-start-2 text-sm text-[var(--color-text-secondary)] sm:col-span-1 sm:col-start-3">
                {rung.meaning}
              </span>
              <span className="col-start-3 row-start-1 justify-self-end font-mono text-base text-[var(--color-text-primary)] sm:col-start-4">
                {rung.ruleCount}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Filed cases                                                        */
/* ------------------------------------------------------------------ */

/** A small labelled block inside an entry — the register's sub-headings. */
function EntryBlock({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-2 border-t border-[var(--color-border)] pt-4 sm:grid-cols-[8.5rem_1fr] sm:gap-6">
      <h4 className={`${RAIL} sm:pt-0.5`}>{label}</h4>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

function FiledCase({ entry }: { entry: CaseEntry }) {
  return (
    <article className="border-t-2 border-[var(--color-text-primary)] py-10 sm:py-14">
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-8">
        <div className="min-w-0 flex-1 basis-[22rem]">
          <p className={RAIL}>
            {entry.ref} · {entry.category} · Illustrative
          </p>
          <p className="mt-4 max-w-[34ch] text-[clamp(1.4rem,3vw,2rem)] font-semibold leading-[1.2] tracking-[-0.02em] text-[var(--color-text-primary)]">
            “{entry.task}”
          </p>
        </div>
        <VerdictStamp level={entry.final} />
      </div>

      <div className="mt-10 grid gap-6">
        <EntryBlock label="Rules fired">
          <ul className="grid gap-3">
            {entry.rules.map((rule) => (
              <li key={rule.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <code className="font-mono text-sm text-[var(--color-accent)]">{rule.id}</code>
                <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--color-text-secondary)]">
                  floor {rule.floor}
                </span>
                <span className="basis-full text-sm text-[var(--color-text-secondary)] sm:basis-auto">
                  {rule.summary}
                </span>
              </li>
            ))}
          </ul>
        </EntryBlock>

        {entry.followups.length > 0 && (
          <EntryBlock label="Asked">
            <ul className="grid gap-4">
              {entry.followups.map((f) => (
                <li key={f.field}>
                  <p className="text-[15px] leading-[1.5] text-[var(--color-text-primary)]">
                    {f.question}
                  </p>
                  <p className="mt-1.5 flex flex-wrap items-baseline gap-x-2.5 text-sm">
                    <span
                      className={`font-mono uppercase tracking-[0.14em] ${
                        f.decisive
                          ? "text-[var(--color-accent)]"
                          : "text-[var(--color-text-secondary)]"
                      }`}
                    >
                      {f.answer}
                    </span>
                    <span className="text-[var(--color-text-secondary)]">{f.effect}</span>
                  </p>
                </li>
              ))}
            </ul>
          </EntryBlock>
        )}

        {/* The composition, written out. This is the product's whole thesis in
            one line, so it is set as an expression rather than prose. */}
        <EntryBlock label="Resolved">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 font-mono text-[15px]">
            <span className="text-[var(--color-text-secondary)]">
              classifier <span className="text-[var(--color-text-primary)]">{entry.ml}</span>
            </span>
            <span className="text-[var(--color-text-secondary)]">
              rules <span className="text-[var(--color-text-primary)]">{entry.rulesResult}</span>
            </span>
            <span className="text-[var(--color-accent)]">max →</span>
            <span
              className="text-lg font-semibold"
              style={{ color: RISK_LEVELS[entry.final].colorVar }}
            >
              {entry.final} {RISK_LEVELS[entry.final].label}
            </span>
          </div>
          <p className="mt-3 max-w-[62ch] text-[15px] leading-[1.6] text-[var(--color-text-secondary)]">
            {entry.shows}
          </p>
        </EntryBlock>
      </div>
    </article>
  );
}

function FiledCases() {
  return (
    <section id="cases" className={`${SHELL} scroll-mt-[60px] pb-8 pt-10`}>
      <div className="max-w-[62ch] pb-10">
        <h2 className="text-[clamp(1.9rem,4.5vw,3rem)] font-semibold leading-[1.06] tracking-[-0.03em] text-[var(--color-text-primary)]">
          Three jobs, filed in full.
        </h2>
        <p className="mt-5 text-[17px] leading-[1.65] text-[var(--color-text-secondary)]">
          Every assessment leaves a record you can read back: what you said, what was
          asked, which hazard rules matched, and how the final level was reached. These
          three are written to show the engine disagreeing with itself. The tasks and
          reference numbers are illustrative — the rule ids, floors and questions are
          quoted from the shipped catalog.
        </p>
      </div>

      {CASES.map((entry) => (
        <FiledCase key={entry.ref} entry={entry} />
      ))}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Standing clauses                                                   */
/* ------------------------------------------------------------------ */

function StandingClauses() {
  return (
    <section
      id="clauses"
      className="scroll-mt-[60px] border-t-2 border-[var(--color-text-primary)] bg-[var(--color-bg-inset)] py-16 sm:py-24"
    >
      <div className={SHELL}>
        <h2 className="max-w-[20ch] text-[clamp(1.9rem,4.5vw,3rem)] font-semibold leading-[1.06] tracking-[-0.03em] text-[var(--color-text-primary)]">
          How a verdict is reached.
        </h2>
        <p className="mt-5 max-w-[62ch] text-[17px] leading-[1.65] text-[var(--color-text-secondary)]">
          These four hold for every assessment. They are enforced in the codebase, not
          configured in a settings panel — there is no admin screen that can loosen them,
          by design.
        </p>

        <ol className="mt-12">
          {CLAUSES.map((clause) => (
            <li
              key={clause.n}
              className="grid gap-x-6 gap-y-3 border-t border-[var(--color-border)] py-8 sm:grid-cols-[4rem_minmax(0,20rem)_1fr]"
            >
              <span className="font-mono text-sm text-[var(--color-accent)]">
                Clause {clause.n}
              </span>
              <h3 className="text-xl font-semibold leading-tight tracking-[-0.02em] text-[var(--color-text-primary)]">
                {clause.title}
              </h3>
              <p className="max-w-[58ch] text-[15px] leading-[1.65] text-[var(--color-text-secondary)]">
                {clause.body}
              </p>
            </li>
          ))}
        </ol>

        {/* Verifiable properties of the shipped system — no usage or accuracy
            claims live on this page, so these are what stands in for them. */}
        <dl className="mt-14 grid gap-x-8 gap-y-8 border-t border-[var(--color-border)] pt-10 sm:grid-cols-2 lg:grid-cols-4">
          {LEDGER_FACTS.map((fact) => (
            <div key={fact.label}>
              <dt className="font-mono text-[clamp(1.5rem,3vw,2rem)] leading-none text-[var(--color-accent)]">
                {fact.value}
              </dt>
              <dd className="mt-3 max-w-[26ch] text-sm leading-[1.55] text-[var(--color-text-secondary)]">
                {fact.label}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Scope note                                                         */
/* ------------------------------------------------------------------ */

function ScopeNote() {
  return (
    <section className={`${SHELL} py-16 sm:py-24`}>
      <div className="grid gap-10 lg:grid-cols-[minmax(0,26rem)_1fr] lg:gap-20">
        <div>
          <h2 className="text-[clamp(1.9rem,4.5vw,3rem)] font-semibold leading-[1.06] tracking-[-0.03em] text-[var(--color-text-primary)]">
            What this register does not cover.
          </h2>
          <p className="mt-5 max-w-[46ch] text-[17px] leading-[1.65] text-[var(--color-text-secondary)]">
            The job ends at the verdict and the kit list. Everything past that point is
            deliberately someone else&apos;s.
          </p>
        </div>

        <ul className="lg:pt-2">
          {OUT_OF_SCOPE.map((item) => (
            <li
              key={item}
              className="flex items-baseline gap-4 border-t border-[var(--color-border)] py-5 text-[17px] leading-[1.5] text-[var(--color-text-secondary)] last:border-b"
            >
              <span aria-hidden="true" className="font-mono text-[var(--color-text-secondary)]/60">
                —
              </span>
              {item}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Close                                                              */
/* ------------------------------------------------------------------ */

function Close() {
  return (
    <section className="border-t-2 border-[var(--color-text-primary)] py-20 sm:py-32">
      <div className={`${SHELL} text-center`}>
        <h2 className="mx-auto max-w-[18ch] text-[clamp(2.1rem,6vw,4rem)] font-semibold leading-[1.02] tracking-[-0.035em] text-[var(--color-text-primary)]">
          Your register is empty. Open it before you start.
        </h2>
        <p className="mx-auto mt-6 max-w-[52ch] text-[17px] leading-[1.65] text-[var(--color-text-secondary)]">
          Describe the job the way you would to a friend. The follow-ups come as
          questions, not a form.
        </p>
        <Link
          href="/chat"
          className="mt-10 inline-flex items-center gap-2 rounded-full bg-[var(--color-accent)] px-7 py-4 text-base font-semibold text-white transition-colors hover:bg-[var(--color-accent-hover)]"
        >
          Start an assessment
          <IconSend width={17} height={17} />
        </Link>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Footer                                                             */
/* ------------------------------------------------------------------ */

function LandingFooter() {
  return (
    <footer className="border-t border-[var(--color-border)] py-10">
      <div
        className={`${SHELL} flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between`}
      >
        <div className="flex items-center gap-2.5">
          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-[var(--color-accent)] text-xs font-bold text-white">
            C
          </span>
          <span className="text-sm font-semibold text-[var(--color-text-primary)]">CanIDIY</span>
        </div>

        <p className="max-w-[58ch] text-[13px] leading-[1.6] text-[var(--color-text-secondary)]">
          Guidance only. CanIDIY assesses risk from what you describe; it does not inspect
          your property, and it is not a substitute for a qualified professional or for
          local building and electrical regulations.
        </p>

        <div className="flex items-center gap-5 text-sm">
          <Link
            href="/login"
            className="text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text-primary)]"
          >
            Sign in
          </Link>
          <Link
            href="/register"
            className="text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text-primary)]"
          >
            Create account
          </Link>
        </div>
      </div>
    </footer>
  );
}

/* ------------------------------------------------------------------ */

export function LandingPage() {
  return (
    /* `shrink-0` is load bearing, not defensive. The root layout's <body> is
       `flex flex-col` and globals.css gives it `height: 100%`, so this element
       is a flex item in a viewport-height column container — and flex items
       default to `flex-shrink: 1`. Without it the box collapses to its
       `min-h-screen` floor while the content overflows, which paints the dark
       ground for exactly one viewport and lets everything below it fall through
       to the (light-themed) body background. */
    <div className="dark min-h-screen shrink-0 bg-[var(--color-bg)] text-[var(--color-text-primary)]">
      <LandingHeader />
      <main>
        <RegisterHead />
        <FiledCases />
        <StandingClauses />
        <ScopeNote />
        <Close />
      </main>
      <LandingFooter />
    </div>
  );
}
