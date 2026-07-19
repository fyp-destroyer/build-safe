"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  IconX,
  IconUser,
  IconSun,
  IconMoon,
  IconMonitor,
  IconDownload,
  IconTrash,
  IconLogOut,
  IconCheck,
} from "@/lib/icons";
import { useTheme } from "@/lib/theme";

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

// Opened from the sidebar's bottom-left profile button. `AnimatePresence`
// here is safe (single conditional child, not `mode="wait"` — see design.md
// §9.1/§12 for when this pattern becomes unsafe).
export function SettingsModal({
  open,
  onClose,
  profile,
  onProfileChange,
  historyCount,
  onClearHistory,
  onExportHistory,
  onLogOut,
  onDeleteAccount,
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
                    tab === t.id
                      ? "bg-[var(--color-accent)] text-white"
                      : "text-[var(--color-text-secondary)] hover:bg-[var(--color-border)]/40 hover:text-[var(--color-text-primary)]"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <div className="relative flex-1 overflow-y-auto p-6">
              <button
                onClick={onClose}
                aria-label="Close settings"
                className="absolute right-4 top-4 flex h-7 w-7 cursor-pointer items-center justify-center rounded-full text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-inset)] hover:text-[var(--color-text-primary)]"
              >
                <IconX width={15} height={15} />
              </button>

              {tab === "profile" && <ProfileTab profile={profile} onProfileChange={onProfileChange} />}
              {tab === "appearance" && <AppearanceTab />}
              {tab === "data" && (
                <DataTab historyCount={historyCount} onClearHistory={onClearHistory} onExportHistory={onExportHistory} />
              )}
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
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm outline-none transition-colors focus:border-[var(--color-accent)]"
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm outline-none transition-colors focus:border-[var(--color-accent)]"
          />
        </label>
      </div>

      <div className="mt-5 flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={!dirty}
          className="cursor-pointer rounded-lg bg-[var(--color-accent)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--color-accent-hover)] disabled:cursor-not-allowed disabled:opacity-40"
        >
          Save changes
        </button>
        <AnimatePresence>
          {saved && (
            <motion.span
              initial={{ opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0 }}
              className="flex items-center gap-1 text-sm text-[var(--color-success)]"
            >
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
        Choose how BuildSafe AI looks. &quot;System&quot; follows your device&apos;s setting automatically.
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

function DataTab({
  historyCount,
  onClearHistory,
  onExportHistory,
}: {
  historyCount: number;
  onClearHistory: () => void;
  onExportHistory: () => void;
}) {
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
        <button
          onClick={onExportHistory}
          disabled={historyCount === 0}
          className="flex shrink-0 cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-sm font-medium transition-colors hover:border-[var(--color-accent)] disabled:cursor-not-allowed disabled:opacity-40"
        >
          <IconDownload width={14} height={14} />
          Export
        </button>
      </div>

      <div className="rounded-lg border border-[var(--color-border)] p-4">
        <div className="mb-3">
          <div className="text-sm font-medium">Clear conversation history</div>
          <div className="text-sm text-[var(--color-text-secondary)]">
            Removes all {historyCount} saved conversations from the sidebar. This can&apos;t be undone.
          </div>
        </div>
        {confirmingClear ? (
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                onClearHistory();
                setConfirmingClear(false);
              }}
              className="cursor-pointer rounded-lg bg-[var(--color-error)] px-3 py-1.5 text-sm font-semibold text-white transition-colors hover:opacity-90"
            >
              Yes, clear history
            </button>
            <button
              onClick={() => setConfirmingClear(false)}
              className="cursor-pointer rounded-lg px-3 py-1.5 text-sm font-medium text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-inset)]"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirmingClear(true)}
            disabled={historyCount === 0}
            className="cursor-pointer rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-sm font-medium transition-colors hover:border-[var(--color-error)] hover:text-[var(--color-error)] disabled:cursor-not-allowed disabled:opacity-40"
          >
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
        <button
          onClick={onLogOut}
          className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-sm font-medium transition-colors hover:border-[var(--color-accent)]"
        >
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
            <button
              onClick={onDeleteAccount}
              className="cursor-pointer rounded-lg bg-[var(--color-error)] px-3 py-1.5 text-sm font-semibold text-white transition-colors hover:opacity-90"
            >
              Yes, delete my account
            </button>
            <button
              onClick={() => setConfirmingDelete(false)}
              className="cursor-pointer rounded-lg px-3 py-1.5 text-sm font-medium text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-inset)]"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirmingDelete(true)}
            className="flex cursor-pointer items-center gap-1.5 rounded-lg bg-[var(--color-error)] px-3 py-1.5 text-sm font-semibold text-white transition-colors hover:opacity-90"
          >
            <IconTrash width={14} height={14} />
            Delete account
          </button>
        )}
      </div>
    </div>
  );
}
