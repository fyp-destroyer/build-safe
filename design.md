# Design System — BuildSafe AI

> **2026-07-18 revision (this version):** rewritten from a prose design spec into an **implementation-ready reference**. A complete working build already exists at [`chat-ui/`](chat-ui) (Vite + React 19 + TypeScript + Tailwind v4 + Motion) — this document is now the annotated source of truth for that implementation, with real code inlined, not aspirational description. If `chat-ui/` and this file ever diverge, treat this file as correct and bring the code back in line with it (or update both together).
>
> **How to use this file:** if you (a fresh Claude Code session, with no other context) are asked to build BuildSafe AI's frontend from scratch in React, this document plus its code snippets is sufficient to reproduce it pixel-for-pixel. Copy the file tree in §3, install the exact dependencies in §2, then work through §6–§11 top to bottom — each section's code block is either the complete file or the complete relevant excerpt. Where a section says "verbatim," paste it as-is; the surrounding prose explains *why* it's shaped that way so you don't "simplify" away a fix for a real bug that was already found and fixed once (see the ⚠️ callouts — every one of them is a bug that actually happened during development, not a hypothetical).

---

## 1. Brand Feel

- The product *is* a conversation with an AI safety assistant — structurally it should feel as familiar and low-friction as ChatGPT, Gemini, or Claude: one message at a time, a fixed sidebar, a bottom composer.
- Visually it must **not** read as a generic AI-chat template. Two deliberate departures from "generic AI chatbot" carry the whole identity:
  1. **Safety-orange + near-black**, not the purple/blue "AI SaaS" palette every chat clone uses. The orange must be *frequent and bold* — primary buttons, active nav states, the send button, card borders, brand marks — not a token accent used once in a corner. Dark mode background is genuinely near-black (`#060606`), not soft charcoal, so the two-tone identity reads at a glance on any screen, including the auth screen before a user is even logged in.
  2. **Inspection-log framing**, not messaging-app framing: monospace per-message timestamps, a fixed marker dot on assistant replies, conversation history grouped by trade category (Electrical, Plumbing, …) instead of by recency, and a risk card that reads as a completed inspection report, not a chat card.
- The five risk-level colors (§4.2) are a **separate, locked functional system** — they carry real safety meaning and must never be reused for brand/decorative purposes, and the brand orange must never be used to imply a risk level. `--risk-4` happens to also be an orange (`#D9772E`) — this is a coincidence the design tolerates (they're visually distinguishable in context: risk-4 only ever appears inside a `RiskChip` pill with an icon+label, never as UI chrome), not a reason to change either color.
- No marketing gradients. Empty/first-load state mirrors ChatGPT/Claude's home screen (centered composer, short greeting, a few example prompts) but the greeting states the product's actual value prop instead of a generic "what are you working on?"

## 2. Tech Stack & Dependencies

Real, verified `package.json` (React 19, Tailwind v4 CSS-first config, no `tailwind.config.js` file):

```json
{
  "dependencies": {
    "clsx": "^2.1.1",
    "motion": "^12.42.2",
    "react": "^19.2.7",
    "react-dom": "^19.2.7",
    "react-router-dom": "^7.18.1",
    "tailwind-merge": "^3.6.0"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4.3.3",
    "@types/node": "^24.13.2",
    "@types/react": "^19.2.17",
    "@types/react-dom": "^19.2.3",
    "@vitejs/plugin-react": "^6.0.3",
    "autoprefixer": "^10.5.4",
    "oxlint": "^1.71.0",
    "postcss": "^8.5.19",
    "tailwindcss": "^4.3.3",
    "typescript": "~6.0.2",
    "vite": "^8.1.1",
    "vite-plugin-singlefile": "^2.3.3"
  }
}
```

**Deliberately not installed:** `lucide-react` (icons are hand-rolled, see §5 — one consistent stroke style, no second icon system mixed in), `three`/`@react-three/fiber` (the auth hero effect is Canvas2D, see §9.2), `framer-motion` (superseded by its renamed successor package `motion`, imported as `motion/react`).

**Why Tailwind v4, not v3:** v4's CSS-first config (`@theme inline` in `index.css`, no `tailwind.config.js`) is what makes the design-token system in §4 work — tokens are plain CSS custom properties on `:root`/`.dark`, re-exposed to Tailwind's utility generator via `@theme inline`. Don't add a `tailwind.config.js`; it isn't read by v4 unless explicitly wired up, and this project has no reason to.

`components.json` (shadcn/21st.dev-compatible config, kept present but not required — allows `npx shadcn@latest add ...` to work without extra setup if ever used):

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": false,
  "tsx": true,
  "tailwind": { "config": "", "css": "src/index.css", "baseColor": "neutral", "cssVariables": true, "prefix": "" },
  "aliases": { "components": "@/components", "utils": "@/lib/utils", "ui": "@/components/ui", "lib": "@/lib", "hooks": "@/hooks" },
  "iconLibrary": "lucide"
}
```

`vite.config.ts` — note the `@/` alias, needed for the `components.json` aliases above and for `cn()`'s canonical import path:

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
})
```

`src/lib/utils.ts` (the canonical shadcn `cn()` helper — most registry components assume this exact path exists):

```ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

**Single-file build for demo/artifact sharing** (optional — `vite.singlefile.config.ts`, separate from the normal dev config, outputs one self-contained HTML file to `dist-singlefile/`):

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

export default defineConfig({
  plugins: [react(), viteSingleFile()],
  build: { outDir: 'dist-singlefile', assetsInlineLimit: 100000000, cssCodeSplit: false },
})
```

## 3. File Tree

```
chat-ui/
  src/
    index.css                          — design tokens + global styles (§4)
    main.tsx                           — entry point, ThemeProvider + HashRouter (§7)
    App.tsx                            — route table (§7)
    lib/
      utils.ts                         — cn() helper (§2)
      theme.tsx                        — light/dark/system theme provider (§8)
      icons.tsx                        — hand-rolled icon set (§5)
      riskLevels.ts                    — locked risk-level → color/icon/label map (§4.2)
      chatData.ts                      — types + demo data (§6)
    components/
      chat/
        Sidebar.tsx                    — §10.1
        MessageBubble.tsx              — §10.2
        RiskCard.tsx                   — §10.3
        Composer.tsx                   — §10.4
        QuickReplyChips.tsx            — §10.5
        TypingIndicator.tsx            — §10.6
      ui/
        RiskChip.tsx                   — §10.7
      settings/
        SettingsModal.tsx              — §10.8
      auth/
        EmailCodeAuth.tsx              — §9.1
        DotMatrixReveal.tsx            — §9.2
    pages/
      ChatPage.tsx                     — §11.1
      LoginPage.tsx                    — §11.2 (trivial: renders EmailCodeAuth mode="login")
      RegisterPage.tsx                 — §11.2 (trivial: renders EmailCodeAuth mode="register")
```

Nothing under `src/assets/` (`hero.png`, default Vite/React SVGs) or `src/App.css` is used — they're inert leftovers from the initial `npm create vite` scaffold and should not be copied into a fresh implementation.

## 4. Design Tokens (`src/index.css`)

This is the **entire** token system and it is the single source of truth for every color used anywhere in the app — no component should ever hardcode a hex value for a themed surface (the one deliberate, documented exception is the always-dark auth screen, §9).

```css
@import "tailwindcss";

@custom-variant dark (&:where(.dark, .dark *));

:root {
  --color-bg: #FFFFFF;
  --color-bg-inset: #F7F7F8;
  --color-surface: #FFFFFF;
  --color-border: #E5E5E5;
  --color-text-primary: #0D0D0D;
  --color-text-secondary: #6E6E80;
  --color-accent: #C2410C;
  --color-accent-hover: #9A3412;
  --color-bubble-user: #F1F1F3;
  --color-success: #16A34A;
  --color-error: #DC2626;
  --risk-1: #2E9E5B;
  --risk-2: #3B82C4;
  --risk-3: #D6A419;
  --risk-4: #D9772E;
  --risk-5: #B3261E;
}

.dark {
  --color-bg: #060606;
  --color-bg-inset: #0F0F10;
  --color-surface: #131314;
  --color-border: #2A2B2E;
  --color-text-primary: #F3F3F3;
  --color-text-secondary: #9B9BA6;
  --color-accent: #F97316;
  --color-accent-hover: #EA580C;
  --color-bubble-user: #221D18;
  --color-success: #22C55E;
  --color-error: #EF4444;
}

@theme inline {
  --color-bg: var(--color-bg);
  --color-bg-inset: var(--color-bg-inset);
  --color-surface: var(--color-surface);
  --color-border: var(--color-border);
  --color-text-primary: var(--color-text-primary);
  --color-text-secondary: var(--color-text-secondary);
  --color-accent: var(--color-accent);
  --color-accent-hover: var(--color-accent-hover);
  --color-bubble-user: var(--color-bubble-user);
  --color-success: var(--color-success);
  --color-error: var(--color-error);
  --color-risk-1: var(--risk-1);
  --color-risk-2: var(--risk-2);
  --color-risk-3: var(--risk-3);
  --color-risk-4: var(--risk-4);
  --color-risk-5: var(--risk-5);
  --font-sans: "Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

* {
  box-sizing: border-box;
}

html, body, #root {
  height: 100%;
}

body {
  font-family: var(--font-sans);
  background: var(--color-bg);
  color: var(--color-text-primary);
  margin: 0;
  -webkit-font-smoothing: antialiased;
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

⚠️ **Bug this file already had once, now fixed:** `SettingsModal.tsx` references `var(--color-success)` and `var(--color-error)` — both tokens must exist in **both** `:root` and `.dark`, and must be re-exposed in `@theme inline`. An earlier revision of this app defined the tokens nowhere at all; the affected UI (the Settings "Saved" checkmark and every destructive button/panel) silently rendered with no color instead of green/red. If you add any new component that needs a semantic (non-risk) success/error color, reuse these two tokens — do not invent a third color system, and do not point them at `--risk-1`/`--risk-5` (see §1 — the two systems must stay independently reusable/renameable).

### 4.1 Token Usage Table

| Token | Light | Dark | Use |
|---|---|---|---|
| `--color-bg` | `#FFFFFF` | `#060606` (near-black) | Main chat column background |
| `--color-bg-inset` | `#F7F7F8` | `#0F0F10` | Sidebar, composer surrounding area, subtle panels |
| `--color-surface` | `#FFFFFF` | `#131314` | Cards (risk card, modals) |
| `--color-border` | `#E5E5E5` | `#2A2B2E` | Dividers, card borders, input borders |
| `--color-text-primary` | `#0D0D0D` | `#F3F3F3` | Body/headline text |
| `--color-text-secondary` | `#6E6E80` | `#9B9BA6` | Captions, metadata, placeholder text |
| `--color-accent` | `#C2410C` | `#F97316` | Primary buttons, active nav state, send button, card borders, brand marks — used **boldly and often**, not sparingly |
| `--color-accent-hover` | `#9A3412` | `#EA580C` | Hover state for every accent-colored control |
| `--color-bubble-user` | `#F1F1F3` | `#221D18` (warmed toward orange) | User message bubble background |
| `--color-success` | `#16A34A` | `#22C55E` | Generic UI success (e.g. Settings "Saved" confirmation) — not a risk color |
| `--color-error` | `#DC2626` | `#EF4444` | Generic UI destructive/error state (delete buttons, confirmations) — not a risk color |

### 4.2 Risk Level Colors — locked, do not reassign

A separate, functional system from the brand palette above (see §1). Defined in `src/lib/riskLevels.ts`, consumed by `RiskChip` (§10.7):

```ts
import type { ComponentType, SVGProps } from "react";
import {
  IconCheckCircle,
  IconUsers,
  IconAlertTriangle,
  IconShieldAlert,
  IconOctagonAlert,
} from "./icons";

export type RiskLevel = 1 | 2 | 3 | 4 | 5;

interface RiskLevelDef {
  level: RiskLevel;
  label: string;
  colorVar: string;
  textVar: string;
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
}

// Locked — never reassign colors/icons, never reorder.
export const RISK_LEVELS: Record<RiskLevel, RiskLevelDef> = {
  1: { level: 1, label: "Safe DIY", colorVar: "var(--risk-1)", textVar: "var(--color-text-primary)", Icon: IconCheckCircle },
  2: { level: 2, label: "DIY with Supervision", colorVar: "var(--risk-2)", textVar: "var(--color-text-primary)", Icon: IconUsers },
  3: { level: 3, label: "Professional Recommended", colorVar: "var(--risk-3)", textVar: "var(--color-text-primary)", Icon: IconAlertTriangle },
  4: { level: 4, label: "Professional Required", colorVar: "var(--risk-4)", textVar: "#fff", Icon: IconShieldAlert },
  5: { level: 5, label: "Dangerous / Do Not Attempt", colorVar: "var(--risk-5)", textVar: "#fff", Icon: IconOctagonAlert },
};
```

| Risk Level | Token | Hex | Icon | Meaning |
|---|---|---|---|---|
| Safe DIY | `--risk-1` | `#2E9E5B` (green) | `IconCheckCircle` | Proceed with normal care |
| DIY with Supervision | `--risk-2` | `#3B82C4` (blue) | `IconUsers` | Proceed with experienced help |
| Professional Recommended | `--risk-3` | `#D6A419` (amber) | `IconAlertTriangle` | Consider hiring a professional |
| Professional Required | `--risk-4` | `#D9772E` (orange) | `IconShieldAlert` | Do not attempt without a professional |
| Dangerous / Do Not Attempt | `--risk-5` | `#B3261E` (red) | `IconOctagonAlert` | Stop; contact a professional immediately |

- Every risk color is always paired with a label + icon inside `RiskChip` — never color alone (color-blind accessibility).
- Minimum contrast 4.5:1: white text on `--risk-4`/`--risk-5`, primary-text-color text on `--risk-1`/`--risk-2`/`--risk-3` (already encoded in `textVar` above).

## 5. Typography & Iconography

**Font:** Inter (variable), loaded via the `@theme inline` `--font-sans` stack in §4, falls back to system sans. One family for everything — headings are Inter at weight 600, body at 400. No separate display/serif face; a chat surface doesn't need one.

| Token | Size / Line height | Use |
|---|---|---|
| `text-xs` (12px) | Metadata, timestamps |
| `text-sm` (14px) | Message bubble text, secondary text — most of the UI lives here |
| `text-base` (16px) | Composer input |
| `text-lg` (18px) | Risk card title |
| `text-xl` (22px) | Empty-state greeting |

**Icons:** one hand-rolled lucide-style stroke icon set in `src/lib/icons.tsx` — **do not** add `lucide-react` or any second icon system; every icon in the app must come from this file. Shared wrapper:

```tsx
import type { SVGProps } from "react";

function Icon({ children, ...props }: SVGProps<SVGSVGElement> & { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      width={props.width ?? 20}
      height={props.height ?? 20}
      {...props}
    >
      {children}
    </svg>
  );
}
```

Every icon is `export const IconX = (p: SVGProps<SVGSVGElement>) => <Icon {...p}><!-- lucide path data --></Icon>`. Full current set (copy path data straight from lucide.dev if recreating from scratch — these are the exact icons used, by name): `IconSend`, `IconPaperclip`, `IconPlus`, `IconChevronRight`, `IconSun`, `IconMoon`, `IconLogOut`, `IconUser`, `IconCheckCircle`, `IconUsers`, `IconAlertTriangle`, `IconShieldAlert`, `IconOctagonAlert`, `IconClock`, `IconDollarSign`, `IconWrench`, `IconAlertCircle`, `IconCheck`, `IconBuilding`, `IconDownload`, `IconMic`, `IconCopy`, `IconEdit`, `IconX`, `IconSettings`, `IconTrash`, `IconMonitor`, and the task-category set `IconBolt`, `IconDroplet`, `IconGrid`, `IconHammer`, `IconBrush`, `IconWind` (Masonry/Roofing/General reuse `IconBuilding`/`IconWrench`/`IconWrench` respectively — see §6).

## 6. Data Model (`src/lib/chatData.ts`)

```ts
import type { RiskLevel } from "./riskLevels";

export type MessageRole = "user" | "assistant";

export interface RiskCardData {
  level: RiskLevel;
  taskTitle: string;
  summary: string;
  factors: string[];
  requiredTools?: string[];
  optionalTools?: string[];
  toolsWithheld?: string;
  cost: string;
  time: string;
  nextStep:
    | { kind: "checklist"; items: string[] }
    | { kind: "consult"; category: string; blurb: string };
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  text?: string;
  quickReplies?: string[];
  riskCard?: RiskCardData;
  createdAt: number;
}

export interface ScriptStep {
  delay: number; // ms of "typing" shown before this step is revealed
  assistantText?: string;
  quickReplies?: string[]; // if present, the script pauses here until the user taps one
  riskCard?: RiskCardData;
}

export interface Scenario {
  id: string;
  title: string;
  userOpening: string;
  steps: ScriptStep[];
}

// Locked task category list — sidebar grouping, icon mapping, and any future
// backend taxonomy must all agree on this exact set and order.
export type TaskCategory =
  | "Electrical" | "Plumbing" | "Carpentry" | "Masonry"
  | "Painting" | "Tiling" | "HVAC" | "Roofing" | "General";

export const CATEGORY_ORDER: TaskCategory[] = [
  "Electrical", "Plumbing", "Carpentry", "Masonry",
  "Painting", "Tiling", "HVAC", "Roofing", "General",
];

export interface HistoryItem {
  id: string;
  title: string;
  category: TaskCategory;
}

// Grouped by task category, not recency — the sidebar reflects what the
// product does (risk assessment by trade), not a generic "Today / Previous 7
// days" chat-history bucket every AI chat tool uses.
export const HISTORY: HistoryItem[] = [
  { id: "h1", title: "Repaint bedroom accent wall", category: "Painting" },
  { id: "h2", title: "Install bathroom exhaust fan", category: "HVAC" },
  { id: "h3", title: "Replace hallway light switch", category: "Electrical" },
  { id: "h4", title: "Re-tile shower floor", category: "Tiling" },
  { id: "h5", title: "Remove load-bearing wall section", category: "Carpentry" },
  { id: "h6", title: "Fix leaking kitchen faucet", category: "Plumbing" },
];

// SCENARIOS: two fully scripted demo conversations (one Safe DIY, one
// Dangerous) used until a real backend exists — see chat-ui/src/lib/chatData.ts
// in the repo for the full step-by-step content (assistant copy, quick
// replies, and both complete RiskCardData objects). Not reproduced in full
// here since it's demo content, not structural design — read it directly
// from the file when wiring up real backend responses in its place.
```

Once a real backend exists, `SCENARIOS` goes away; everything that consumes `RiskCardData`/`ChatMessage` (Sidebar, MessageBubble, RiskCard, ChatPage) stays the same — they only depend on the shape, not the scripted content.

## 7. Routing & App Shell

`HashRouter`, not `BrowserRouter` — required if the build is ever served as a static `file://` HTML bundle (e.g. single-file artifact export): `BrowserRouter` reads `window.location.pathname`, which becomes the full filesystem path in that context and matches no route. `HashRouter` uses the URL fragment instead and works identically regardless of hosting path. Keep `HashRouter` even for a normal server-hosted deployment — there's no downside and it avoids ever having to remember to switch back.

`src/main.tsx`:

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import './index.css'
import App from './App.tsx'
import { ThemeProvider } from './lib/theme.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <HashRouter>
        <App />
      </HashRouter>
    </ThemeProvider>
  </StrictMode>,
)
```

`src/App.tsx`:

```tsx
import { Navigate, Route, Routes } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import ChatPage from "./pages/ChatPage";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/chat" element={<ChatPage />} />
    </Routes>
  );
}

export default App;
```

## 8. Theme System (`src/lib/theme.tsx`)

Three-way `light | dark | system` choice, persisted to `localStorage`, live-updates when the OS preference changes while `system` is selected:

```tsx
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

type Resolved = "light" | "dark";
type ThemeChoice = Resolved | "system";

interface ThemeContextValue {
  theme: Resolved; // the actual applied theme — always resolved, never "system"
  themeChoice: ThemeChoice; // the stored preference, including "system" — drives Settings UI
  setThemeChoice: (choice: ThemeChoice) => void;
  toggle: () => void; // quick toggle for screens with no Settings access
}

const STORAGE_KEY = "buildsafe-theme-choice";
const ThemeContext = createContext<ThemeContextValue | null>(null);

function getSystemPref(): Resolved {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function getInitialChoice(): ThemeChoice {
  if (typeof window === "undefined") return "system";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark" || stored === "system") return stored;
  return "system";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [themeChoice, setThemeChoiceState] = useState<ThemeChoice>(getInitialChoice);
  const [systemPref, setSystemPref] = useState<Resolved>(() =>
    typeof window === "undefined" ? "light" : getSystemPref()
  );

  useEffect(() => {
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => setSystemPref(getSystemPref());
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);

  const theme: Resolved = themeChoice === "system" ? systemPref : themeChoice;

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  const setThemeChoice = (choice: ThemeChoice) => {
    setThemeChoiceState(choice);
    window.localStorage.setItem(STORAGE_KEY, choice);
  };

  const toggle = () => setThemeChoice(theme === "dark" ? "light" : "dark");

  return (
    <ThemeContext.Provider value={{ theme, themeChoice, setThemeChoice, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
```

The `.dark` class toggle on `document.documentElement` is what activates the `.dark { ... }` token overrides in §4 via the `@custom-variant dark` selector in `index.css`.

## 9. Auth Screens

### 9.1 `EmailCodeAuth.tsx` — shared login/register flow

One component drives both `/login` and `/register` via a `mode` prop; `LoginPage`/`RegisterPage` are one-line wrappers (§11.2). Flow: email step → 6-digit code step → success step, each a cross-faded `motion.div`. **Deliberately always-dark** regardless of the app's light/dark theme choice (hardcoded `bg-black`/`text-white`, not theme tokens) — this is a one-off hero moment, not reachable via the theme toggle, so it uses **literal orange hex values** (`#F97316`/`#EA580C`) rather than `var(--color-accent)`, since that CSS var would resolve to whichever shade the *app's* current theme happens to be in, and this screen intentionally ignores that setting.

```tsx
import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { useNavigate } from "react-router-dom";
import { DotMatrixReveal } from "./DotMatrixReveal";
import { IconCheck, IconSend } from "../../lib/icons";

type Step = "email" | "code" | "success";
type Mode = "login" | "register";

const COPY: Record<Mode, { emailTitle: string; emailSubtitle: string; successTitle: string; successSubtitle: string; cta: string }> = {
  login: {
    emailTitle: "Welcome back",
    emailSubtitle: "Sign in to continue",
    successTitle: "You're in!",
    successSubtitle: "Welcome back to BuildSafe AI",
    cta: "Continue to Chat",
  },
  register: {
    emailTitle: "Create your account",
    emailSubtitle: "Get started with BuildSafe AI",
    successTitle: "Account created",
    successSubtitle: "Welcome to BuildSafe AI",
    cta: "Continue to Chat",
  },
};

export function EmailCodeAuth({ mode }: { mode: Mode }) {
  const copy = COPY[mode];
  const navigate = useNavigate();

  const [step, setStep] = useState<Step>("email");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState(["", "", "", "", "", ""]);
  const [reverseVisible, setReverseVisible] = useState(false);
  const [initialVisible, setInitialVisible] = useState(true);
  const codeInputRefs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    if (step === "code") {
      const t = setTimeout(() => codeInputRefs.current[0]?.focus(), 400);
      return () => clearTimeout(t);
    }
  }, [step]);

  const handleEmailSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (email) setStep("code");
  };

  const handleCodeChange = (index: number, value: string) => {
    if (value.length > 1) return;
    const next = [...code];
    next[index] = value;
    setCode(next);

    if (value && index < 5) codeInputRefs.current[index + 1]?.focus();

    if (index === 5 && value && next.every((d) => d.length === 1)) {
      setReverseVisible(true);
      setTimeout(() => setInitialVisible(false), 50);
      setTimeout(() => setStep("success"), 1400);
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !code[index] && index > 0) {
      codeInputRefs.current[index - 1]?.focus();
    }
  };

  const handleBack = () => {
    setStep("email");
    setCode(["", "", "", "", "", ""]);
    setReverseVisible(false);
    setInitialVisible(true);
  };

  const codeComplete = code.every((d) => d !== "");

  return (
    <div className="relative flex min-h-screen w-full flex-col items-center justify-center overflow-hidden text-white">
      <div className="absolute inset-0">
        {initialVisible && <DotMatrixReveal reverse={false} animationSpeed={3} />}
        {reverseVisible && <DotMatrixReveal reverse animationSpeed={4} />}
      </div>

      <div className="absolute left-6 top-6 z-10 flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#F97316] text-sm font-bold text-white">B</div>
        <span className="text-sm font-semibold text-white/90">BuildSafe AI</span>
      </div>

      <div className="relative z-10 w-full max-w-sm px-4">
        {(
          step === "email" ? (
            <motion.div
              key="email-step"
              initial={{ opacity: 0, x: -60 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.35, ease: "easeOut" }}
              className="space-y-6 text-center"
            >
              <div className="space-y-1">
                <h1 className="text-3xl font-bold tracking-tight">{copy.emailTitle}</h1>
                <p className="text-lg font-light text-white/60">{copy.emailSubtitle}</p>
              </div>

              <div className="space-y-4">
                <button
                  type="button"
                  className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-3 text-sm text-white backdrop-blur-sm transition-colors hover:bg-white/10"
                >
                  <span className="text-base font-semibold">G</span>
                  {mode === "login" ? "Sign in with Google" : "Sign up with Google"}
                </button>

                <div className="flex items-center gap-4">
                  <div className="h-px flex-1 bg-white/10" />
                  <span className="text-sm text-white/40">or</span>
                  <div className="h-px flex-1 bg-white/10" />
                </div>

                {mode === "register" && (
                  <input
                    type="text"
                    placeholder="Full name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full rounded-full border border-white/10 bg-transparent px-4 py-3 text-center text-white outline-none backdrop-blur-sm placeholder:text-white/40 focus:border-white/30"
                  />
                )}

                <form onSubmit={handleEmailSubmit}>
                  <div className="relative">
                    <input
                      type="email"
                      placeholder="you@example.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      className="w-full rounded-full border border-white/10 bg-transparent px-4 py-3 text-center text-white outline-none backdrop-blur-sm placeholder:text-white/40 focus:border-white/30"
                    />
                    <button
                      type="submit"
                      aria-label="Continue"
                      className="absolute right-1.5 top-1.5 flex h-9 w-9 cursor-pointer items-center justify-center rounded-full bg-[#F97316] text-white transition-colors hover:bg-[#EA580C]"
                    >
                      <IconSend width={15} height={15} />
                    </button>
                  </div>
                </form>
              </div>

              <p className="pt-6 text-xs text-white/40">
                By continuing, you agree to BuildSafe AI's Terms and Privacy Notice.
              </p>

              <p className="text-sm text-white/50">
                {mode === "login" ? (
                  <>
                    Don't have an account?{" "}
                    <a href="#/register" className="font-semibold text-[#F97316] hover:text-[#FB923C]">
                      Sign up
                    </a>
                  </>
                ) : (
                  <>
                    Already have an account?{" "}
                    <a href="#/login" className="font-semibold text-[#F97316] hover:text-[#FB923C]">
                      Log in
                    </a>
                  </>
                )}
              </p>
            </motion.div>
          ) : step === "code" ? (
            <motion.div
              key="code-step"
              initial={{ opacity: 0, x: 60 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.35, ease: "easeOut" }}
              className="space-y-6 text-center"
            >
              <div className="space-y-1">
                <h1 className="text-3xl font-bold tracking-tight">We sent you a code</h1>
                <p className="text-lg font-light text-white/50">Check {email || "your email"}</p>
              </div>

              <div className="rounded-full border border-white/10 px-5 py-4 transition-colors focus-within:border-[#F97316]/50">
                <div className="flex items-center justify-center gap-1">
                  {code.map((digit, i) => (
                    <div key={i} className="flex items-center">
                      <div className="relative">
                        <input
                          ref={(el) => {
                            codeInputRefs.current[i] = el;
                          }}
                          type="text"
                          inputMode="numeric"
                          maxLength={1}
                          value={digit}
                          onChange={(e) => handleCodeChange(i, e.target.value)}
                          onKeyDown={(e) => handleKeyDown(i, e)}
                          style={{ caretColor: "transparent" }}
                          className="w-8 border-none bg-transparent text-center text-xl text-white outline-none"
                        />
                        {!digit && (
                          <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-xl text-white/20">
                            0
                          </div>
                        )}
                      </div>
                      {i < 5 && <span className="text-xl text-white/20">|</span>}
                    </div>
                  ))}
                </div>
              </div>

              <p className="cursor-pointer text-sm text-white/50 transition-colors hover:text-white/70">Resend code</p>

              <div className="flex w-full gap-3">
                <button
                  onClick={handleBack}
                  className="w-[30%] cursor-pointer rounded-full border border-white/15 py-3 font-medium text-white transition-colors hover:bg-white/10"
                >
                  Back
                </button>
                <button
                  disabled={!codeComplete}
                  className={`flex-1 cursor-pointer rounded-full border py-3 font-medium transition-all ${
                    codeComplete
                      ? "border-transparent bg-[#F97316] text-white hover:bg-[#EA580C]"
                      : "cursor-not-allowed border-white/10 bg-[#111] text-white/50"
                  }`}
                >
                  Continue
                </button>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="success-step"
              initial={{ opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, ease: "easeOut", delay: 0.2 }}
              className="space-y-6 text-center"
            >
              <div className="space-y-1">
                <h1 className="text-3xl font-bold tracking-tight">{copy.successTitle}</h1>
                <p className="text-lg font-light text-white/50">{copy.successSubtitle}</p>
              </div>

              <motion.div
                initial={{ scale: 0.7, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ duration: 0.4, delay: 0.35 }}
                className="py-6"
              >
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[#F97316]">
                  <IconCheck width={26} height={26} className="text-white" />
                </div>
              </motion.div>

              <motion.button
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.7 }}
                onClick={() => navigate("/chat")}
                className="w-full cursor-pointer rounded-full bg-[#F97316] py-3 font-medium text-white transition-colors hover:bg-[#EA580C]"
              >
                {copy.cta}
              </motion.button>
            </motion.div>
          )
        )}
      </div>
    </div>
  );
}
```

⚠️ **Do not wrap these three steps in `<AnimatePresence mode="wait">`.** An earlier revision did, to get a proper exit-then-enter sequence between steps, and it **deadlocked**: React state updated correctly (confirmed via direct Fiber inspection) but the DOM stayed frozen on the previous step forever, because the exit-completion callback never resolved under React 19 + `StrictMode` in this setup. The fix — and the state of the code above — is to drop `mode="wait"` (and the `exit` prop, which is then unusable without it) and let steps cross-fade via plain `initial`/`animate` instead. If you need true sequential exit-then-enter elsewhere in this codebase, test `mode="wait"` in total isolation first; treat it as broken-until-proven-otherwise in this stack, not just in this one component.

Secondary actions (the Google sign-in button, the "Back" button) are deliberately left neutral/outlined, not orange — giving every button the same weight as the primary CTA would flatten the hierarchy the accent color is trying to create.

### 9.2 `DotMatrixReveal.tsx` — Canvas2D hero animation

A Canvas2D re-implementation of a WebGL dot-matrix reveal effect (a wave of dots fading in from the center, or fading out from the edges inward on `reverse`) — deliberately not using `three`/`@react-three/fiber`, since the visual is fundamentally a 2D grid animation and doesn't need a 3D engine.

```tsx
import { useEffect, useRef } from "react";

export function DotMatrixReveal({
  reverse = false,
  animationSpeed = 3,
  dotSize = 3,
  cellSize = 20,
}: {
  reverse?: boolean;
  animationSpeed?: number;
  dotSize?: number;
  cellSize?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let width = 0;
    let height = 0;
    let cols = 0;
    let rows = 0;
    let rand: Float32Array = new Float32Array(0);
    let opacityTier: Float32Array = new Float32Array(0);

    const OPACITIES = [0.3, 0.3, 0.3, 0.5, 0.5, 0.5, 0.8, 0.8, 0.8, 1];

    function hash(x: number, y: number) {
      const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453123;
      return s - Math.floor(s);
    }

    function resize() {
      if (!canvas) return;
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);

      cols = Math.ceil(width / cellSize) + 1;
      rows = Math.ceil(height / cellSize) + 1;
      rand = new Float32Array(cols * rows);
      opacityTier = new Float32Array(cols * rows);
      for (let j = 0; j < rows; j++) {
        for (let i = 0; i < cols; i++) {
          const idx = j * cols + i;
          rand[idx] = hash(i, j);
          opacityTier[idx] = OPACITIES[Math.floor(hash(i + 0.5, j + 0.5) * OPACITIES.length)];
        }
      }
    }

    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    let raf = 0;
    let start = performance.now();

    function frame(now: number) {
      if (!ctx) return;
      // Recomputed every frame (cheap) — see ⚠️ note below for why this can't
      // be hoisted outside the loop.
      const centerCol = cols / 2;
      const centerRow = rows / 2;
      const maxDist = Math.hypot(centerCol, centerRow);
      const t = ((now - start) / 1000) * animationSpeed * 0.35;
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, width, height);

      for (let j = 0; j < rows; j++) {
        for (let i = 0; i < cols; i++) {
          const idx = j * cols + i;
          const dist = Math.hypot(i - centerCol, j - centerRow);
          let opacity: number;

          if (reduceMotion) {
            opacity = opacityTier[idx];
          } else if (reverse) {
            const offset = (maxDist - dist) * 0.35 + rand[idx] * 2.2;
            opacity = t > offset ? 0 : opacityTier[idx];
          } else {
            const offset = dist * 0.35 + rand[idx] * 2.2;
            opacity = t > offset ? opacityTier[idx] : 0;
          }

          if (opacity <= 0.01) continue;
          ctx.globalAlpha = opacity;
          ctx.fillStyle = "#F97316"; // brand orange dots, not white — see §1
          ctx.beginPath();
          ctx.arc(i * cellSize + cellSize / 2, j * cellSize + cellSize / 2, dotSize / 2, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1;

      if (!reduceMotion) raf = requestAnimationFrame(frame);
    }

    raf = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [reverse, animationSpeed, dotSize, cellSize]);

  return (
    <div className="absolute inset-0 overflow-hidden bg-black">
      <canvas ref={canvasRef} className="h-full w-full" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_transparent_0%,_rgba(0,0,0,0.6)_100%)]" />
      <div className="absolute inset-x-0 top-0 h-1/3 bg-gradient-to-b from-black to-transparent" />
    </div>
  );
}
```

⚠️ **`centerCol`/`centerRow`/`maxDist` must be computed inside `frame()`, every frame — not once outside the render loop.** An earlier revision computed them once, synchronously, right after the very first `resize()` call — before the canvas had actually laid out, when `clientWidth`/`clientHeight` were still `0`. Every subsequent, correctly-sized `resize()` (from the `ResizeObserver`) updated `cols`/`rows` but never touched the already-frozen center point, so the canvas rendered pure black forever — no dots ever appeared, at any wait duration. The fix is exactly the 3-line recompute shown above; it's cheap enough to not matter for performance. If you ever refactor this to "optimize" by hoisting that calculation back out of the loop, you will reintroduce this exact bug.

## 10. Chat Components

### 10.1 `Sidebar.tsx`

Fixed 260px width, category-grouped history (not recency-grouped — see §1), solid-orange "New chat" CTA, active item marked with both a background wash and a left accent bar (not just a faint tint — needs to be unmistakable), name-in-bottom-left opens `SettingsModal`.

```tsx
import { useState } from "react";
import { motion } from "motion/react";
import { useNavigate } from "react-router-dom";
import { CATEGORY_ORDER, type HistoryItem, type TaskCategory } from "../../lib/chatData";
import {
  IconPlus, IconLogOut, IconUser,
  IconBolt, IconDroplet, IconHammer, IconBuilding, IconBrush, IconGrid, IconWind, IconWrench,
} from "../../lib/icons";
import { SettingsModal, type Profile } from "../settings/SettingsModal";

const CATEGORY_ICON: Record<TaskCategory, typeof IconBolt> = {
  Electrical: IconBolt,
  Plumbing: IconDroplet,
  Carpentry: IconHammer,
  Masonry: IconBuilding,
  Painting: IconBrush,
  Tiling: IconGrid,
  HVAC: IconWind,
  Roofing: IconBuilding,
  General: IconWrench,
};

export function Sidebar({
  activeId, onNewChat, onSelectHistory, history, profile, onProfileChange,
  onClearHistory, onExportHistory, onDeleteAccount,
}: {
  activeId: string | null;
  onNewChat: () => void;
  onSelectHistory: (id: string) => void;
  history: HistoryItem[];
  profile: Profile;
  onProfileChange: (profile: Profile) => void;
  onClearHistory: () => void;
  onExportHistory: () => void;
  onDeleteAccount: () => void;
}) {
  const navigate = useNavigate();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const handleLogOut = () => navigate("/login");

  return (
    <aside className="flex h-full w-[260px] shrink-0 flex-col gap-4 border-r border-[var(--color-border)] bg-[var(--color-bg-inset)] p-3">
      <div className="flex items-center gap-2 px-2 pt-1">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--color-accent)] text-sm font-bold text-white">
          B
        </div>
        <span className="text-sm font-semibold">BuildSafe AI</span>
      </div>

      <button
        onClick={onNewChat}
        className="flex cursor-pointer items-center gap-2 rounded-lg bg-[var(--color-accent)] px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--color-accent-hover)]"
      >
        <IconPlus width={16} height={16} />
        New chat
      </button>

      <nav className="flex-1 overflow-y-auto">
        {CATEGORY_ORDER.map((category) => {
          const items = history.filter((h) => h.category === category);
          if (items.length === 0) return null;
          const CategoryIcon = CATEGORY_ICON[category];
          return (
            <div key={category} className="mb-3">
              <div className="flex items-center gap-1.5 px-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-secondary)]">
                <CategoryIcon width={11} height={11} className="text-[var(--color-accent)]" />
                {category}
              </div>
              <div className="flex flex-col gap-0.5">
                {items.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => onSelectHistory(item.id)}
                    className={`relative truncate rounded-lg py-1.5 pl-2.5 pr-2.5 text-left text-sm transition-colors ${
                      activeId === item.id
                        ? "font-medium text-[var(--color-text-primary)]"
                        : "text-[var(--color-text-secondary)] hover:bg-[var(--color-border)]/40 hover:text-[var(--color-text-primary)]"
                    }`}
                  >
                    {activeId === item.id && (
                      <motion.div
                        layoutId="active-history"
                        className="absolute inset-0 rounded-lg bg-[var(--color-accent)]/15"
                        transition={{ type: "spring", stiffness: 500, damping: 40 }}
                      />
                    )}
                    {activeId === item.id && (
                      <motion.div
                        layoutId="active-history-bar"
                        className="absolute inset-y-1 left-0 w-[3px] rounded-full bg-[var(--color-accent)]"
                        transition={{ type: "spring", stiffness: 500, damping: 40 }}
                      />
                    )}
                    <span className="relative">{item.title}</span>
                  </button>
                ))}
              </div>
            </div>
          );
        })}
        {history.length === 0 && (
          <div className="px-2.5 py-1.5 text-sm text-[var(--color-text-secondary)]">No saved conversations</div>
        )}
      </nav>

      <div className="border-t border-[var(--color-border)] pt-2">
        <div className="flex items-center justify-between rounded-lg px-2.5 py-2 transition-colors hover:bg-[var(--color-border)]/40">
          <button onClick={() => setSettingsOpen(true)} className="flex cursor-pointer items-center gap-2 text-sm font-medium">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--color-accent)]/15 text-[var(--color-accent)]">
              <IconUser width={14} height={14} />
            </span>
            {profile.name}
          </button>
          <button onClick={handleLogOut} aria-label="Log out" className="cursor-pointer text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]">
            <IconLogOut width={16} height={16} />
          </button>
        </div>
      </div>

      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        profile={profile}
        onProfileChange={onProfileChange}
        historyCount={history.length}
        onClearHistory={onClearHistory}
        onExportHistory={onExportHistory}
        onLogOut={handleLogOut}
        onDeleteAccount={onDeleteAccount}
      />
    </aside>
  );
}
```

### 10.2 `MessageBubble.tsx`

User bubbles: right-aligned, `--color-bubble-user` background, hover-revealed Edit/Copy icon buttons, monospace timestamp. Assistant messages: left-aligned, no bubble, a fixed orange marker dot ("inspector's log" framing — see §1), same monospace timestamp.

```tsx
import { useState } from "react";
import { motion } from "motion/react";
import type { ChatMessage } from "../../lib/chatData";
import { IconCopy, IconEdit, IconCheck } from "../../lib/icons";

function formatTime(ts: number) {
  return new Date(ts).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

export function MessageBubble({ message, onEdit }: { message: ChatMessage; onEdit?: (id: string, text: string) => void }) {
  const isUser = message.role === "user";
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.text ?? "");
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!message.text) return;
    try {
      await navigator.clipboard.writeText(message.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API can reject without permission/HTTPS — nothing else to do here.
    }
  };

  const startEdit = () => { setDraft(message.text ?? ""); setEditing(true); };
  const cancelEdit = () => { setDraft(message.text ?? ""); setEditing(false); };
  const saveEdit = () => {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== message.text) onEdit?.(message.id, trimmed);
    setEditing(false);
  };

  if (isUser && editing) {
    return (
      <div className="flex justify-end">
        <div className="w-full max-w-[80%] rounded-2xl bg-[var(--color-bubble-user)] p-3">
          <textarea
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); saveEdit(); }
              else if (e.key === "Escape") cancelEdit();
            }}
            rows={Math.min(8, Math.max(1, draft.split("\n").length))}
            className="w-full resize-none bg-transparent text-sm text-[var(--color-text-primary)] outline-none"
          />
          <div className="mt-2 flex justify-end gap-2">
            <button type="button" onClick={cancelEdit} className="cursor-pointer rounded-full px-3 py-1 text-xs font-medium text-[var(--color-text-secondary)] transition-colors hover:bg-black/5 dark:hover:bg-white/10">
              Cancel
            </button>
            <button type="button" onClick={saveEdit} className="cursor-pointer rounded-full bg-[var(--color-accent)] px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-[var(--color-accent-hover)]">
              Save
            </button>
          </div>
        </div>
      </div>
    );
  }

  const timeLabel = <span className="font-mono text-[10px] tracking-tight text-[var(--color-text-secondary)]">{formatTime(message.createdAt)}</span>;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className={`group flex flex-col ${isUser ? "items-end" : "items-start"}`}
    >
      {isUser ? (
        <>
          <div className="max-w-[80%] whitespace-pre-wrap break-words rounded-2xl bg-[var(--color-bubble-user)] px-3.5 py-2 text-sm text-[var(--color-text-primary)]">
            {message.text}
          </div>
          <div className="mt-1 flex items-center gap-2">
            <div className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
              <button type="button" onClick={startEdit} aria-label="Edit message" className="flex h-6 w-6 cursor-pointer items-center justify-center rounded-md text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-inset)] hover:text-[var(--color-text-primary)]">
                <IconEdit width={13} height={13} />
              </button>
              <button type="button" onClick={handleCopy} aria-label="Copy message" className="flex h-6 w-6 cursor-pointer items-center justify-center rounded-md text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-inset)] hover:text-[var(--color-text-primary)]">
                {copied ? <IconCheck width={13} height={13} /> : <IconCopy width={13} height={13} />}
              </button>
            </div>
            {timeLabel}
          </div>
        </>
      ) : (
        <div className="flex max-w-[90%] items-start gap-2.5">
          <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-accent)]" aria-hidden />
          <div className="flex flex-col gap-1">
            <div className="whitespace-pre-wrap break-words text-sm leading-relaxed text-[var(--color-text-primary)]">
              {message.text}
            </div>
            {timeLabel}
          </div>
        </div>
      )}
    </motion.div>
  );
}
```

Note: edit deliberately does **not** truncate/regenerate subsequent messages the way ChatGPT's edit does — it just updates the displayed text. In this demo build the assistant replies are a fixed scenario script, not derived from message content, so faking a "regenerate" would misrepresent what's happening; once a real backend exists, decide this behavior deliberately rather than copying ChatGPT's pattern by default.

### 10.3 `RiskCard.tsx`

The single highest-information-density moment in the product — gets the app's one deliberate motion flourish (a scan-sweep on reveal) that nothing else gets, per the "spend boldness in one place" principle.

```tsx
import { motion, useReducedMotion } from "motion/react";
import type { RiskCardData } from "../../lib/chatData";
import { RiskChip } from "../ui/RiskChip";
import { IconAlertCircle, IconWrench, IconDollarSign, IconClock, IconCheck, IconBuilding, IconDownload } from "../../lib/icons";

export function RiskCard({ data }: { data: RiskCardData }) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      initial={{ opacity: 0, y: 12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="relative mt-2 w-full max-w-[560px] overflow-hidden rounded-xl border border-[var(--color-accent)]/25 bg-[var(--color-surface)] p-6"
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
          <button className="mt-4 flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--color-accent)]/40 px-3 py-1.5 text-xs font-semibold text-[var(--color-accent)] transition-colors hover:bg-[var(--color-accent)]/10">
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
```

`data.nextStep` is a discriminated union: `{ kind: "checklist", items }` for low-risk DIY tasks, or `{ kind: "consult", category, blurb }` for anything Professional-Recommended-or-above — the product recommends hiring a professional but does not connect the user to one in-app (no quote/marketplace feature exists).

### 10.4 `Composer.tsx`

```tsx
import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { IconPaperclip, IconSend, IconMic } from "../../lib/icons";

export function Composer({ onSend, disabled, autoFocus }: { onSend: (text: string) => void; disabled?: boolean; autoFocus?: boolean }) {
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
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
          }}
          placeholder="Message BuildSafe AI…"
          className="max-h-[160px] w-full resize-none overflow-y-auto bg-transparent px-4 pt-3.5 pb-1 text-[15px] leading-relaxed outline-none placeholder:text-[var(--color-text-secondary)] disabled:opacity-50"
        />
        <div className="flex items-center justify-between px-2 pb-2 pt-1">
          <button type="button" aria-label="Attach photo" className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-full text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-inset)]">
            <IconPaperclip width={17} height={17} />
          </button>
          <div className="flex items-center gap-1">
            <button type="button" aria-label="Voice input" className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-full text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-inset)]">
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
```

⚠️ **This exact two-layer wrapper structure is required** for the composer bar to line up pixel-for-pixel with the message thread above it (§11.1 uses the identical structure for the message list). Two separate bugs happened here and both are now baked into the shape of the code above:

1. **Padding must live on the outer, unconstrained wrapper** (`w-full overflow-y-hidden px-4 pb-4`), never inside the inner `mx-auto max-w-[680px]` box. If the inner box also has its own horizontal padding, it shrinks below `680px` while the message column's identically-labeled `max-w-[680px]` box has zero internal padding — both report the same max-width class but render at visibly different actual widths, offset from each other.
2. **`[scrollbar-gutter:stable]` alone does nothing on a non-scrolling element.** The message list above it scrolls and has a real vertical scrollbar eating ~15px from its content width; `scrollbar-gutter: stable` only takes effect on elements that are already scroll containers (`overflow` ≠ `visible`). The composer wrapper needs `overflow-y-hidden` *in addition to* `[scrollbar-gutter:stable]` — that makes it a (non-scrolling, nothing to clip) scroll container so the gutter reservation actually applies, matching the message list's reserved space exactly. Without both together, the composer sits ~7–8px offset from the message column even though both boxes report identical `max-w-[680px]`.

If you ever need to move the composer to a different visual context, keep this whole two-`div` shape — don't "simplify" it to one div with padding+max-width combined, or both bugs come back.

### 10.5 `QuickReplyChips.tsx`

```tsx
import { motion } from "motion/react";

export function QuickReplyChips({ options, onSelect, disabled }: { options: string[]; onSelect: (option: string) => void; disabled?: boolean }) {
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
```

Used for the safety-critical yes/no/not-sure follow-up questions — tapping one sends it as the next user message, identical to typing it.

### 10.6 `TypingIndicator.tsx`

```tsx
import { motion } from "motion/react";

export function TypingIndicator() {
  return (
    <div className="flex items-center gap-1.5 py-1">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="h-1.5 w-1.5 rounded-full bg-[var(--color-text-secondary)]"
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{ duration: 1.1, repeat: Infinity, delay: i * 0.12, ease: "easeInOut" }}
        />
      ))}
    </div>
  );
}
```

### 10.7 `RiskChip.tsx`

```tsx
import { RISK_LEVELS, type RiskLevel } from "../../lib/riskLevels";

const SIZES = {
  sm: { pad: "4px 10px 4px 8px", font: "12px", icon: 14 },
  md: { pad: "6px 14px 6px 10px", font: "13px", icon: 16 },
  xl: { pad: "14px 24px 14px 16px", font: "22px", icon: 26 },
} as const;

export function RiskChip({ level, size = "md", showLabel = true }: { level: RiskLevel; size?: keyof typeof SIZES; showLabel?: boolean }) {
  const def = RISK_LEVELS[level];
  const s = SIZES[size];
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full font-semibold"
      style={{ background: def.colorVar, color: def.textVar, padding: s.pad, fontSize: s.font }}
    >
      <def.Icon width={s.icon} height={s.icon} className="shrink-0" />
      {showLabel && <span>{def.label}</span>}
    </span>
  );
}
```

Note this component uses inline `style` (not Tailwind classes) for the risk color, since the color is chosen dynamically from `RISK_LEVELS` — Tailwind can't statically generate a class for a runtime-selected CSS variable.

### 10.8 `SettingsModal.tsx`

Opened by clicking the profile name in the sidebar's bottom-left. Four tabs: Profile, Appearance, Data, Account. `AnimatePresence` here is safe (single conditional child, not `mode="wait"` — see the ⚠️ warning in §9.1, this component doesn't hit that bug because it's not sequencing between multiple *sibling* animated steps).

```tsx
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  IconX, IconUser, IconSun, IconMoon, IconMonitor, IconDownload, IconTrash, IconLogOut, IconCheck,
} from "../../lib/icons";
import { useTheme } from "../../lib/theme";

export interface Profile {
  name: string;
  email: string;
}

type Tab = "profile" | "appearance" | "data" | "account";

const TABS: { id: Tab; label: string }[] = [
  { id: "profile", label: "Profile" },
  { id: "appearance", label: "Appearance" },
  { id: "data", label: "Data" },
  { id: "account", label: "Account" },
];

export function SettingsModal({
  open, onClose, profile, onProfileChange, historyCount, onClearHistory, onExportHistory, onLogOut, onDeleteAccount,
}: {
  open: boolean;
  onClose: () => void;
  profile: Profile;
  onProfileChange: (profile: Profile) => void;
  historyCount: number;
  onClearHistory: () => void;
  onExportHistory: () => void;
  onLogOut: () => void;
  onDeleteAccount: () => void;
}) {
  const [tab, setTab] = useState<Tab>("profile");

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.97, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 8 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="Settings"
            className="flex h-[540px] w-full max-w-[720px] overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-xl"
          >
            <div className="flex w-[190px] shrink-0 flex-col gap-1 border-r border-[var(--color-border)] bg-[var(--color-bg-inset)] p-3">
              <h2 className="px-2 pb-2 pt-1 text-sm font-semibold">Settings</h2>
              {TABS.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  className={`cursor-pointer rounded-lg px-2.5 py-2 text-left text-sm font-medium transition-colors ${
                    tab === t.id ? "bg-[var(--color-accent)] text-white" : "text-[var(--color-text-secondary)] hover:bg-[var(--color-border)]/40 hover:text-[var(--color-text-primary)]"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <div className="relative flex-1 overflow-y-auto p-6">
              <button onClick={onClose} aria-label="Close settings" className="absolute right-4 top-4 flex h-7 w-7 cursor-pointer items-center justify-center rounded-full text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-inset)] hover:text-[var(--color-text-primary)]">
                <IconX width={15} height={15} />
              </button>

              {tab === "profile" && <ProfileTab profile={profile} onProfileChange={onProfileChange} />}
              {tab === "appearance" && <AppearanceTab />}
              {tab === "data" && <DataTab historyCount={historyCount} onClearHistory={onClearHistory} onExportHistory={onExportHistory} />}
              {tab === "account" && <AccountTab onLogOut={onLogOut} onDeleteAccount={onDeleteAccount} />}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function SectionTitle({ children }: { children: string }) {
  return <h3 className="mb-4 text-lg font-semibold">{children}</h3>;
}

function ProfileTab({ profile, onProfileChange }: { profile: Profile; onProfileChange: (profile: Profile) => void }) {
  const [name, setName] = useState(profile.name);
  const [email, setEmail] = useState(profile.email);
  const [saved, setSaved] = useState(false);
  const dirty = name !== profile.name || email !== profile.email;

  const handleSave = () => {
    onProfileChange({ name: name.trim() || profile.name, email: email.trim() || profile.email });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div>
      <SectionTitle>Profile</SectionTitle>
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[var(--color-bg-inset)] text-[var(--color-text-secondary)]">
          <IconUser width={24} height={24} />
        </div>
        <div className="text-sm text-[var(--color-text-secondary)]">
          Your name and email are shown in the sidebar and used to personalize your assessments.
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm outline-none transition-colors focus:border-[var(--color-accent)]" />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Email</span>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm outline-none transition-colors focus:border-[var(--color-accent)]" />
        </label>
      </div>

      <div className="mt-5 flex items-center gap-3">
        <button onClick={handleSave} disabled={!dirty} className="cursor-pointer rounded-lg bg-[var(--color-accent)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--color-accent-hover)] disabled:cursor-not-allowed disabled:opacity-40">
          Save changes
        </button>
        <AnimatePresence>
          {saved && (
            <motion.span initial={{ opacity: 0, x: -4 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} className="flex items-center gap-1 text-sm text-[var(--color-success)]">
              <IconCheck width={14} height={14} /> Saved
            </motion.span>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function AppearanceTab() {
  const { themeChoice, setThemeChoice } = useTheme();
  const options: { id: "light" | "dark" | "system"; label: string; icon: typeof IconSun }[] = [
    { id: "light", label: "Light", icon: IconSun },
    { id: "dark", label: "Dark", icon: IconMoon },
    { id: "system", label: "System", icon: IconMonitor },
  ];

  return (
    <div>
      <SectionTitle>Appearance</SectionTitle>
      <p className="mb-4 text-sm text-[var(--color-text-secondary)]">
        Choose how BuildSafe AI looks. "System" follows your device's setting automatically.
      </p>
      <div className="grid grid-cols-3 gap-3">
        {options.map((opt) => {
          const Icon = opt.icon;
          const active = themeChoice === opt.id;
          return (
            <button
              key={opt.id}
              onClick={() => setThemeChoice(opt.id)}
              className={`flex cursor-pointer flex-col items-center gap-2 rounded-xl border p-4 transition-colors ${
                active ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10" : "border-[var(--color-border)] hover:bg-[var(--color-bg-inset)]"
              }`}
            >
              <Icon width={20} height={20} className={active ? "text-[var(--color-accent)]" : "text-[var(--color-text-secondary)]"} />
              <span className={`text-sm font-medium ${active ? "text-[var(--color-accent)]" : ""}`}>{opt.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function DataTab({ historyCount, onClearHistory, onExportHistory }: { historyCount: number; onClearHistory: () => void; onExportHistory: () => void }) {
  const [confirmingClear, setConfirmingClear] = useState(false);

  return (
    <div>
      <SectionTitle>Data</SectionTitle>

      <div className="mb-5 flex items-center justify-between rounded-lg border border-[var(--color-border)] p-4">
        <div>
          <div className="text-sm font-medium">Export assessment history</div>
          <div className="text-sm text-[var(--color-text-secondary)]">
            Download your {historyCount} saved assessment{historyCount === 1 ? "" : "s"} as a JSON file.
          </div>
        </div>
        <button onClick={onExportHistory} disabled={historyCount === 0} className="flex shrink-0 cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-sm font-medium transition-colors hover:border-[var(--color-accent)] disabled:cursor-not-allowed disabled:opacity-40">
          <IconDownload width={14} height={14} />
          Export
        </button>
      </div>

      <div className="rounded-lg border border-[var(--color-border)] p-4">
        <div className="mb-3">
          <div className="text-sm font-medium">Clear conversation history</div>
          <div className="text-sm text-[var(--color-text-secondary)]">
            Removes all {historyCount} saved conversations from the sidebar. This can't be undone.
          </div>
        </div>
        {confirmingClear ? (
          <div className="flex items-center gap-2">
            <button onClick={() => { onClearHistory(); setConfirmingClear(false); }} className="cursor-pointer rounded-lg bg-[var(--color-error)] px-3 py-1.5 text-sm font-semibold text-white transition-colors hover:opacity-90">
              Yes, clear history
            </button>
            <button onClick={() => setConfirmingClear(false)} className="cursor-pointer rounded-lg px-3 py-1.5 text-sm font-medium text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-inset)]">
              Cancel
            </button>
          </div>
        ) : (
          <button onClick={() => setConfirmingClear(true)} disabled={historyCount === 0} className="cursor-pointer rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-sm font-medium transition-colors hover:border-[var(--color-error)] hover:text-[var(--color-error)] disabled:cursor-not-allowed disabled:opacity-40">
            Clear history
          </button>
        )}
      </div>
    </div>
  );
}

function AccountTab({ onLogOut, onDeleteAccount }: { onLogOut: () => void; onDeleteAccount: () => void }) {
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  return (
    <div>
      <SectionTitle>Account</SectionTitle>

      <div className="mb-5 flex items-center justify-between rounded-lg border border-[var(--color-border)] p-4">
        <div className="text-sm font-medium">Log out of BuildSafe AI</div>
        <button onClick={onLogOut} className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-sm font-medium transition-colors hover:border-[var(--color-accent)]">
          <IconLogOut width={14} height={14} />
          Log out
        </button>
      </div>

      <div className="rounded-lg border border-[var(--risk-5)]/30 bg-[var(--risk-5)]/5 p-4">
        <div className="mb-3">
          <div className="text-sm font-medium text-[var(--color-error)]">Delete account</div>
          <div className="text-sm text-[var(--color-text-secondary)]">
            Permanently deletes your account and all assessment history. This cannot be undone.
          </div>
        </div>
        {confirmingDelete ? (
          <div className="flex items-center gap-2">
            <button onClick={onDeleteAccount} className="cursor-pointer rounded-lg bg-[var(--color-error)] px-3 py-1.5 text-sm font-semibold text-white transition-colors hover:opacity-90">
              Yes, delete my account
            </button>
            <button onClick={() => setConfirmingDelete(false)} className="cursor-pointer rounded-lg px-3 py-1.5 text-sm font-medium text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-inset)]">
              Cancel
            </button>
          </div>
        ) : (
          <button onClick={() => setConfirmingDelete(true)} className="flex cursor-pointer items-center gap-1.5 rounded-lg bg-[var(--color-error)] px-3 py-1.5 text-sm font-semibold text-white transition-colors hover:opacity-90">
            <IconTrash width={14} height={14} />
            Delete account
          </button>
        )}
      </div>
    </div>
  );
}
```

Note the destructive controls (Clear history, Delete account) use `--color-error`, **never** `--color-accent` — even under the "more orange" brand push (§1), conflating the brand color with the danger color would undermine a safety product's own semantics. This restraint is deliberate, not an oversight.

## 11. Pages

### 11.1 `ChatPage.tsx`

The main app shell: `Sidebar` + a flex column that's either the empty state (centered composer + greeting + suggestion chips) or the scrolling message thread + bottom-pinned composer.

```tsx
import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useNavigate } from "react-router-dom";
import { Sidebar } from "../components/chat/Sidebar";
import { Composer } from "../components/chat/Composer";
import { MessageBubble } from "../components/chat/MessageBubble";
import { QuickReplyChips } from "../components/chat/QuickReplyChips";
import { RiskCard } from "../components/chat/RiskCard";
import { TypingIndicator } from "../components/chat/TypingIndicator";
import { SCENARIOS, HISTORY, type ChatMessage, type Scenario, type HistoryItem } from "../lib/chatData";
import type { Profile } from "../components/settings/SettingsModal";

const SUGGESTIONS = SCENARIOS.map((s) => ({ id: s.id, title: s.title }));

let idCounter = 0;
const nextId = () => `m-${++idCounter}`;

export default function ChatPage() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [activeScenario, setActiveScenario] = useState<Scenario | null>(null);
  const [awaitingReplyOptions, setAwaitingReplyOptions] = useState<string[] | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [activeHistoryId, setActiveHistoryId] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>(HISTORY);
  const [profile, setProfile] = useState<Profile>({ name: "Jane Doe", email: "jane@example.com" });
  const currentStepRef = useRef(0);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isTyping]);

  const runStep = useCallback((scenario: Scenario, index: number) => {
    const step = scenario.steps[index];
    if (!step) return;
    setIsTyping(true);
    setAwaitingReplyOptions(null);
    window.setTimeout(() => {
      currentStepRef.current = index;
      setIsTyping(false);
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "assistant", text: step.assistantText, riskCard: step.riskCard, createdAt: Date.now() },
      ]);
      if (step.quickReplies) {
        setAwaitingReplyOptions(step.quickReplies);
      } else if (index + 1 < scenario.steps.length) {
        runStep(scenario, index + 1);
      }
    }, step.delay);
  }, []);

  const startScenario = (scenario: Scenario) => {
    setActiveHistoryId(null);
    setMessages([{ id: nextId(), role: "user", text: scenario.userOpening, createdAt: Date.now() }]);
    setActiveScenario(scenario);
    currentStepRef.current = -1;
    runStep(scenario, 0);
  };

  const handleSend = (text: string) => {
    if (awaitingReplyOptions) { handleQuickReply(text); return; }
    const matched = SCENARIOS.find((s) => text.toLowerCase().includes("bathroom") || text.toLowerCase().includes("wir")) ?? SCENARIOS[0];
    setMessages((prev) => [...prev, { id: nextId(), role: "user", text, createdAt: Date.now() }]);
    setActiveScenario(matched);
    currentStepRef.current = -1;
    runStep(matched, 0);
  };

  const handleQuickReply = (option: string) => {
    if (!activeScenario) return;
    setAwaitingReplyOptions(null);
    setMessages((prev) => [...prev, { id: nextId(), role: "user", text: option, createdAt: Date.now() }]);
    runStep(activeScenario, currentStepRef.current + 1);
  };

  const handleEditMessage = (id: string, text: string) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, text } : m)));
  };

  const handleNewChat = () => {
    setMessages([]);
    setActiveScenario(null);
    currentStepRef.current = 0;
    setAwaitingReplyOptions(null);
    setActiveHistoryId(null);
  };

  const handleClearHistory = () => { setHistory([]); setActiveHistoryId(null); };

  const handleExportHistory = () => {
    const blob = new Blob([JSON.stringify(history, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "buildsafe-assessment-history.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDeleteAccount = () => {
    setHistory([]);
    setMessages([]);
    setActiveHistoryId(null);
    navigate("/login");
  };

  const isEmpty = messages.length === 0;

  return (
    <div className="flex h-screen bg-[var(--color-bg)] text-[var(--color-text-primary)]">
      <Sidebar
        activeId={activeHistoryId}
        onNewChat={handleNewChat}
        onSelectHistory={setActiveHistoryId}
        history={history}
        profile={profile}
        onProfileChange={setProfile}
        onClearHistory={handleClearHistory}
        onExportHistory={handleExportHistory}
        onDeleteAccount={handleDeleteAccount}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        {isEmpty ? (
          <div className="flex flex-1 flex-col items-center justify-center px-4">
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="mb-6 flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-accent)] text-sm font-bold text-white">
                B
              </div>
              <h1 className="text-xl font-semibold">Describe the task. We'll tell you if it's safe.</h1>
            </motion.div>
            <div className="w-full max-w-[680px]">
              <Composer onSend={handleSend} autoFocus />
              <div className="mt-3 flex flex-wrap justify-center gap-2 px-4">
                {SUGGESTIONS.map((s, i) => (
                  <motion.button
                    key={s.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 + i * 0.05 }}
                    onClick={() => startScenario(SCENARIOS[i])}
                    className="cursor-pointer rounded-full border border-[var(--color-accent)]/25 px-3.5 py-1.5 text-sm text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)]/10 hover:text-[var(--color-text-primary)]"
                  >
                    {s.title}
                  </motion.button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6 [scrollbar-gutter:stable]">
              <div className="relative mx-auto flex max-w-[680px] flex-col gap-4">
                <div aria-hidden className="pointer-events-none absolute -left-4 bottom-0 top-0 w-px bg-[var(--color-accent)]/25" />
                <AnimatePresence initial={false}>
                  {messages.map((m) => (
                    <div key={m.id} className="flex flex-col gap-2">
                      {m.text && <MessageBubble message={m} onEdit={handleEditMessage} />}
                      {m.riskCard && <RiskCard data={m.riskCard} />}
                    </div>
                  ))}
                </AnimatePresence>

                {isTyping && (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start">
                    <TypingIndicator />
                  </motion.div>
                )}

                {awaitingReplyOptions && !isTyping && (
                  <div className="flex justify-start">
                    <QuickReplyChips options={awaitingReplyOptions} onSelect={handleQuickReply} />
                  </div>
                )}
              </div>
            </div>
            <Composer onSend={handleSend} disabled={!!awaitingReplyOptions || isTyping} />
          </>
        )}
      </div>
    </div>
  );
}
```

⚠️ **`currentStepRef` is a ref, not state, on purpose.** `runStep`'s own `setTimeout` chain auto-advances through scripted steps; React state set inside that chain would be stale by the time a later closure (e.g. `handleQuickReply`, called from a completely separate event) reads it. The ref sidesteps the staleness.

⚠️ **`{m.text && <MessageBubble .../>}` is a required guard, not a stylistic choice.** Messages that carry only a `riskCard` (no `assistantText`) must not render `MessageBubble` at all — an earlier revision rendered it unconditionally, which produced a floating marker-dot-and-timestamp row with no visible text above the risk card, since `MessageBubble` always renders its marker/timestamp chrome regardless of whether there's text to go with it.

The message-thread's outer scroll container (`px-4 py-6 [scrollbar-gutter:stable]`) and the composer's outer wrapper (§10.4) must keep the same padding/scrollbar-gutter pairing — see the ⚠️ note in §10.4 for why.

### 11.2 `LoginPage.tsx` / `RegisterPage.tsx`

```tsx
// LoginPage.tsx
import { EmailCodeAuth } from "../components/auth/EmailCodeAuth";
export default function LoginPage() {
  return <EmailCodeAuth mode="login" />;
}
```

```tsx
// RegisterPage.tsx
import { EmailCodeAuth } from "../components/auth/EmailCodeAuth";
export default function RegisterPage() {
  return <EmailCodeAuth mode="register" />;
}
```

## 12. Motion Conventions

Using `motion` (the renamed `framer-motion`), imported as `motion/react` throughout.

| Moment | Treatment |
|---|---|
| New message enters | fade + 8px upward slide, 200ms ease-out (`MessageBubble`) |
| Risk card reveal | slightly slower (300ms) than a plain message, plus the one-off scan-sweep flourish (§10.3) — this is the product's single most important moment, it gets its own beat |
| Typing indicator | looping opacity pulse on three dots, staggered 120ms apart |
| Quick-reply chips | staggered entrance, ~40ms between chips |
| Sidebar active-item highlight | shared-layout (`layoutId`) spring transition between list items, not an instant jump |
| Composer send button | scale+opacity animate between disabled/enabled, not mount/unmount |
| Settings modal | `AnimatePresence` fade+scale, single conditional child (safe — see the `mode="wait"` warning in §9.1 for when this pattern becomes unsafe) |
| Auth step transitions | cross-fade via plain `initial`/`animate` — explicitly **not** `AnimatePresence mode="wait"`, see §9.1 |

All motion must respect `prefers-reduced-motion` (handled globally in `index.css` §4 for CSS transitions/animations, and via `useReducedMotion()` explicitly in `RiskCard` and `DotMatrixReveal` for JS-driven animation that the global CSS override can't reach).

## 13. Accessibility Baseline

- WCAG AA minimum contrast across all text, in both light and dark themes.
- All interactive elements keyboard-navigable and focus-visible — quick-reply chips, sidebar items, Settings tabs, and the composer's send/attach/mic buttons included.
- Risk level always conveyed through icon + text + color together (`RiskChip`), never color alone.
- Respect `prefers-reduced-motion` everywhere per §12.
- Settings modal: `role="dialog"`, `aria-modal="true"`, `aria-label="Settings"`, closes on `Escape` and on backdrop click.

## 14. What This Doc Deliberately Does Not Specify

- **Real backend integration.** `SCENARIOS` in `chatData.ts` is scripted demo content standing in for a real API — nothing else in the design depends on it being scripted; swapping it for real streamed responses only touches `ChatPage.tsx`'s `runStep`/`handleSend`/`handleQuickReply`, not any component in §10.
- **The old `mockups/` static-HTML prototype and the user dashboard.** Those predate this React implementation and use a different (superseded) visual language; they are not part of what this document specifies and should not be used as a reference if they still exist in the repo.
- **Backend-facing concerns** (auth security, rate limiting, the actual safety-rule/ML classification pipeline) — see `architecture.md`, `rules.md`, and `prd.md` instead. This document is frontend-presentation-only.
