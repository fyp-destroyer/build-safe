"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import { type HistoryItem, type TaskCategory } from "@/lib/chatData";
import { useClerk } from "@clerk/nextjs";
import {
  IconPlus,
  IconLogOut,
  IconUser,
  IconStar,
  IconBolt,
  IconDroplet,
  IconHammer,
  IconBuilding,
  IconBrush,
  IconGrid,
  IconWind,
  IconWrench,
  IconTrash,
  IconX,
} from "@/lib/icons";
import { SettingsModal, type Profile } from "@/components/settings/SettingsModal";

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

// Fixed 260px width, recency-ordered history split into two sections —
// Favourites (starred items, top) and Chats (everything else, bottom) —
// solid-orange "New chat" CTA, active item marked with both a background
// wash and a left accent bar so it's unmistakable — see design.md §10.1.
export function Sidebar({
  activeId,
  onNewChat,
  onSelectHistory,
  history,
  onToggleFavourite,
  onDeleteHistory,
  profile,
  onProfileChange,
  onClearHistory,
  onExportHistory,
  onDeleteAccount,
}: {
  activeId: string | null;
  onNewChat: () => void;
  onSelectHistory: (id: string) => void;
  history: HistoryItem[];
  onToggleFavourite: (id: string) => void;
  onDeleteHistory: (id: string) => void;
  profile: Profile;
  onProfileChange: (profile: Profile) => void;
  onClearHistory: () => void;
  onExportHistory: () => void;
  onDeleteAccount: () => void;
}) {
  const router = useRouter();
  const { signOut } = useClerk();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const handleLogOut = () => {
    // Clerk revokes the session server-side and clears its cookie, so the next
    // request is genuinely unauthenticated. The old version only removed a
    // localStorage key — the token itself stayed valid for its full 30-day life
    // with no revocation list, so "log out" was local housekeeping rather than
    // an actual end of session.
    void signOut(() => router.push("/login"));
  };

  const byRecency = (a: HistoryItem, b: HistoryItem) => b.createdAt - a.createdAt;
  const favourites = history.filter((h) => h.favourite).sort(byRecency);
  const chats = history.filter((h) => !h.favourite).sort(byRecency);

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
        {favourites.length > 0 && (
          <HistorySection
            label="Favourites"
            items={favourites}
            activeId={activeId}
            onSelectHistory={onSelectHistory}
            onToggleFavourite={onToggleFavourite}
            onDeleteHistory={onDeleteHistory}
          />
        )}
        {chats.length > 0 && (
          <HistorySection
            label="Chats"
            items={chats}
            activeId={activeId}
            onSelectHistory={onSelectHistory}
            onToggleFavourite={onToggleFavourite}
            onDeleteHistory={onDeleteHistory}
          />
        )}
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

function HistorySection({
  label,
  items,
  activeId,
  onSelectHistory,
  onToggleFavourite,
  onDeleteHistory,
}: {
  label: string;
  items: HistoryItem[];
  activeId: string | null;
  onSelectHistory: (id: string) => void;
  onToggleFavourite: (id: string) => void;
  onDeleteHistory: (id: string) => void;
}) {
  // Deleting a conversation also deletes its assessment server-side and
  // can't be undone, so it takes two clicks: the trash icon swaps the row
  // for an inline "Delete?" confirmation. Inline rather than window.confirm
  // — a native modal blocks the whole page and looks nothing like the rest
  // of the app.
  const [confirmingId, setConfirmingId] = useState<string | null>(null);

  return (
    <div className="mb-3">
      <div className="px-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-secondary)]">
        {label}
      </div>
      <div className="flex flex-col gap-0.5">
        {items.map((item) => {
          const CategoryIcon = CATEGORY_ICON[item.category];
          return (
            <div
              key={item.id}
              className={`group relative flex items-center gap-1 rounded-lg pl-2.5 pr-1.5 transition-colors ${
                activeId === item.id ? "" : "hover:bg-[var(--color-border)]/40"
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
              <button
                onClick={() => onSelectHistory(item.id)}
                className="relative min-w-0 flex-1 truncate py-1.5 text-left"
              >
                <div
                  className={`truncate text-sm ${
                    activeId === item.id ? "font-medium text-[var(--color-text-primary)]" : "text-[var(--color-text-secondary)]"
                  }`}
                >
                  {item.title}
                </div>
                <div className="flex items-center gap-1 text-[11px] text-[var(--color-accent)]">
                  <CategoryIcon width={10} height={10} />
                  {item.category}
                </div>
              </button>
              {confirmingId === item.id ? (
                <div className="relative flex shrink-0 items-center gap-1">
                  <button
                    onClick={() => {
                      setConfirmingId(null);
                      onDeleteHistory(item.id);
                    }}
                    aria-label={`Confirm delete ${item.title}`}
                    className="cursor-pointer rounded-md bg-[var(--color-error)] px-1.5 py-0.5 text-[11px] font-semibold text-white"
                  >
                    Delete
                  </button>
                  <button
                    onClick={() => setConfirmingId(null)}
                    aria-label="Cancel delete"
                    className="cursor-pointer p-1 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
                  >
                    <IconX width={13} height={13} />
                  </button>
                </div>
              ) : (
                <>
                  <button
                    onClick={() => onToggleFavourite(item.id)}
                    aria-label={item.favourite ? "Remove from favourites" : "Add to favourites"}
                    className={`relative shrink-0 cursor-pointer p-1 transition-colors ${
                      item.favourite
                        ? "text-[var(--color-accent)]"
                        : "text-[var(--color-text-secondary)] opacity-0 group-hover:opacity-100 hover:text-[var(--color-accent)]"
                    }`}
                  >
                    <IconStar width={14} height={14} fill={item.favourite ? "currentColor" : "none"} />
                  </button>
                  <button
                    onClick={() => setConfirmingId(item.id)}
                    aria-label={`Delete ${item.title}`}
                    className="relative shrink-0 cursor-pointer p-1 text-[var(--color-text-secondary)] opacity-0 transition-colors group-hover:opacity-100 hover:text-[var(--color-error)]"
                  >
                    <IconTrash width={14} height={14} />
                  </button>
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
