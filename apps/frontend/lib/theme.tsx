"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

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
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function getInitialChoice(): ThemeChoice {
  if (typeof window === "undefined") return "system";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark" || stored === "system")
    return stored;
  return "system";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [themeChoice, setThemeChoiceState] = useState<ThemeChoice>(
    getInitialChoice
  );
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
    <ThemeContext.Provider
      value={{ theme, themeChoice, setThemeChoice, toggle }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
