import { Database, FileJson, HardHat, ShieldAlert, Wrench } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { getSeedData } from "../services/api";
import type { SeedDataResponse } from "../types/assessment";

type SeedTab = "tools" | "materials" | "safety_rules" | "professional_categories";

interface TabConfig {
  key: SeedTab;
  label: string;
  icon: typeof Wrench;
}

const tabs: TabConfig[] = [
  { key: "tools", label: "Tools", icon: Wrench },
  { key: "materials", label: "Materials", icon: FileJson },
  { key: "safety_rules", label: "Safety rules", icon: ShieldAlert },
  { key: "professional_categories", label: "Professionals", icon: HardHat },
];

export function AdminSeedDataPanel(): JSX.Element {
  const [seedData, setSeedData] = useState<SeedDataResponse | null>(null);
  const [activeTab, setActiveTab] = useState<SeedTab>("tools");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadSeedData(): Promise<void> {
      try {
        setIsLoading(true);
        setError(null);
        const payload = await getSeedData(controller.signal);
        setSeedData(payload);
      } catch (caughtError) {
        if (controller.signal.aborted) {
          return;
        }
        setError(caughtError instanceof Error ? caughtError.message : "Unable to load seed data");
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    }

    void loadSeedData();
    return () => controller.abort();
  }, []);

  const activeJson = useMemo(() => {
    if (!seedData) {
      return "";
    }
    return JSON.stringify(seedData[activeTab], null, 2);
  }, [activeTab, seedData]);

  const counts = seedData
    ? {
        tools: Object.keys(seedData.tools).length,
        materials: Object.keys(seedData.materials).length,
        safety_rules: seedData.safety_rules.length,
        professional_categories: Object.keys(seedData.professional_categories).length,
      }
    : null;

  return (
    <section className="rounded-md border border-zinc-200 bg-white p-6 shadow-panel">
      <div className="flex flex-col gap-4 border-b border-zinc-200 pb-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex items-start gap-3">
          <Database aria-hidden="true" className="mt-0.5 h-6 w-6 text-teal-700" />
          <div>
            <h2 className="text-lg font-bold text-zinc-950">Admin Seed Data</h2>
            <p className="mt-1 text-sm leading-6 text-zinc-600">
              Read-only JSON editor placeholder for the MVP catalogs and rules.
            </p>
          </div>
        </div>
        {counts ? (
          <div className="grid grid-cols-2 gap-2 text-xs font-semibold text-zinc-600 sm:grid-cols-4">
            <CountBadge label="Tools" value={counts.tools} />
            <CountBadge label="Materials" value={counts.materials} />
            <CountBadge label="Rules" value={counts.safety_rules} />
            <CountBadge label="Pros" value={counts.professional_categories} />
          </div>
        ) : null}
      </div>

      <div className="mt-5 flex flex-wrap gap-2" role="tablist" aria-label="Seed data sections">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => setActiveTab(tab.key)}
              className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-semibold transition ${
                isActive
                  ? "border-zinc-950 bg-zinc-950 text-white"
                  : "border-zinc-200 bg-zinc-50 text-zinc-700 hover:border-zinc-300"
              }`}
            >
              <Icon aria-hidden="true" className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      <div className="mt-4">
        {isLoading ? (
          <p className="rounded-md border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm text-zinc-600">
            Loading seed data...
          </p>
        ) : error ? (
          <p className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>
        ) : (
          <textarea
            aria-label={`${activeTab} JSON`}
            readOnly
            value={activeJson}
            className="min-h-80 w-full resize-y rounded-md border border-zinc-300 bg-zinc-950 px-4 py-3 font-mono text-xs leading-5 text-zinc-100 outline-none"
          />
        )}
      </div>
    </section>
  );
}

interface CountBadgeProps {
  label: string;
  value: number;
}

function CountBadge({ label, value }: CountBadgeProps): JSX.Element {
  return (
    <span className="rounded-md border border-zinc-200 bg-zinc-50 px-2.5 py-1 text-center">
      {label}: {value}
    </span>
  );
}
