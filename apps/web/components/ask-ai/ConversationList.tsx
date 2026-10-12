"use client";

import { MessageSquare, MoreHorizontal, Plus } from "lucide-react";
import { useRef, useState } from "react";
import {
  formatConversationTime,
  groupConversations,
  type AskConversation,
} from "@/lib/ask-ai";
import { useClickOutside } from "@/lib/use-click-outside";
import { askAI } from "./strings";

export function NewChatButton({ onClick, disabled }: { onClick: () => void; disabled?: boolean }) {
  return (
    <button type="button" className="primary-button w-full text-sm" disabled={disabled} onClick={onClick}>
      <Plus size={16} /> {askAI.newChat.replace("+ ", "")}
    </button>
  );
}

function ConversationItem({
  conversation,
  active,
  onSelect,
  onRename,
  onDelete,
}: {
  conversation: AskConversation;
  active: boolean;
  onSelect: () => void;
  onRename: (title: string) => void;
  onDelete: () => void;
}) {
  const [menu, setMenu] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, menu, () => setMenu(false));

  return (
    <div
      className={`group relative flex items-center gap-1 rounded-lg ${
        active ? "bg-blue-50 dark:bg-blue-950/40" : "hover:bg-surface-muted/70"
      }`}
      ref={ref}
    >
      <button
        type="button"
        className="flex min-w-0 flex-1 items-center gap-2 px-2 py-1.5 text-left"
        onClick={onSelect}
        title={conversation.title}
      >
        <MessageSquare size={14} className="shrink-0 text-muted" />
        <span className="min-w-0 flex-1 truncate text-sm text-foreground">{conversation.title}</span>
        <span className="shrink-0 text-[11px] text-muted">
          {formatConversationTime(conversation.updated_at || conversation.created_at)}
        </span>
      </button>
      <button
        type="button"
        className="icon-button h-7 w-7 opacity-0 group-hover:opacity-100"
        onClick={() => setMenu((v) => !v)}
        aria-label="Conversation actions"
      >
        <MoreHorizontal size={14} />
      </button>
      {menu ? (
        <div className="absolute right-1 top-8 z-20 w-36 rounded-lg border border-border bg-surface p-1 shadow-lg">
          <button
            type="button"
            className="menu-link w-full text-left"
            onClick={() => {
              setMenu(false);
              const next = window.prompt(askAI.rename, conversation.title);
              if (next && next.trim()) onRename(next.trim());
            }}
          >
            {askAI.rename}
          </button>
          <button
            type="button"
            className="menu-link w-full text-left text-rose-600"
            onClick={() => {
              setMenu(false);
              if (window.confirm(askAI.deleteConfirm)) onDelete();
            }}
          >
            {askAI.delete}
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function ConversationList({
  conversations,
  activeId,
  onSelect,
  onRename,
  onDelete,
}: {
  conversations: AskConversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
}) {
  const groups = groupConversations(conversations);
  if (!groups.length) {
    return <p className="px-1 py-2 text-xs text-muted">No conversations yet.</p>;
  }
  return (
    <div className="space-y-3">
      {groups.map((g) => (
        <div key={g.key}>
          <p className="mb-1 px-1 text-[11px] font-semibold uppercase tracking-wide text-muted">
            {g.key === "today" ? askAI.today : g.key === "recent" ? askAI.recent : g.label}
          </p>
          <ul className="space-y-0.5">
            {g.items.map((c) => (
              <li key={c.id}>
                <ConversationItem
                  conversation={c}
                  active={activeId === c.id}
                  onSelect={() => onSelect(c.id)}
                  onRename={(title) => onRename(c.id, title)}
                  onDelete={() => onDelete(c.id)}
                />
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
