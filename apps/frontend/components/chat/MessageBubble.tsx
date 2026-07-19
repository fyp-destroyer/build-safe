"use client";

import { useState } from "react";
import { motion } from "motion/react";
import type { ChatMessage } from "@/lib/chatData";
import { IconCopy, IconEdit, IconCheck } from "@/lib/icons";

function formatTime(ts: number) {
  return new Date(ts).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

export function MessageBubble({
  message,
  onEdit,
}: {
  message: ChatMessage;
  onEdit?: (id: string, text: string) => void;
}) {
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

  const startEdit = () => {
    setDraft(message.text ?? "");
    setEditing(true);
  };
  const cancelEdit = () => {
    setDraft(message.text ?? "");
    setEditing(false);
  };
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
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                saveEdit();
              } else if (e.key === "Escape") cancelEdit();
            }}
            rows={Math.min(8, Math.max(1, draft.split("\n").length))}
            className="w-full resize-none bg-transparent text-sm text-[var(--color-text-primary)] outline-none"
          />
          <div className="mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={cancelEdit}
              className="cursor-pointer rounded-full px-3 py-1 text-xs font-medium text-[var(--color-text-secondary)] transition-colors hover:bg-black/5 dark:hover:bg-white/10"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={saveEdit}
              className="cursor-pointer rounded-full bg-[var(--color-accent)] px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-[var(--color-accent-hover)]"
            >
              Save
            </button>
          </div>
        </div>
      </div>
    );
  }

  const timeLabel = (
    <span className="font-mono text-[10px] tracking-tight text-[var(--color-text-secondary)]">
      {formatTime(message.createdAt)}
    </span>
  );

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
              <button
                type="button"
                onClick={startEdit}
                aria-label="Edit message"
                className="flex h-6 w-6 cursor-pointer items-center justify-center rounded-md text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-inset)] hover:text-[var(--color-text-primary)]"
              >
                <IconEdit width={13} height={13} />
              </button>
              <button
                type="button"
                onClick={handleCopy}
                aria-label="Copy message"
                className="flex h-6 w-6 cursor-pointer items-center justify-center rounded-md text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-inset)] hover:text-[var(--color-text-primary)]"
              >
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
