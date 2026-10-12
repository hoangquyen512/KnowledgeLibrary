"use client";

import { ChevronLeft, PanelLeft } from "lucide-react";
import type { Space, Workspace } from "@/lib/api";
import type { AskConversation } from "@/lib/ask-ai";
import { AiBrandIcon } from "@/components/brand";
import { ConversationList, NewChatButton } from "./ConversationList";
import { SpaceScopeSelector } from "./SpaceScopeSelector";
import { WorkspaceSelector } from "./WorkspaceSelector";
import { askAI } from "./strings";

export function AskAISidebar({
  collapsed,
  onToggleCollapsed,
  workspaces,
  workspaceId,
  onWorkspaceChange,
  workspaceLocked,
  lockScope,
  lockedSpaceName,
  spaces,
  selectedSpaces,
  onToggleSpace,
  onSelectAllSpaces,
  onNewChat,
  newChatDisabled,
  conversations,
  activeConversationId,
  onSelectConversation,
  onRenameConversation,
  onDeleteConversation,
  mode,
}: {
  collapsed: boolean;
  onToggleCollapsed: () => void;
  workspaces: Workspace[];
  workspaceId: string;
  onWorkspaceChange: (id: string) => void;
  workspaceLocked?: boolean;
  lockScope?: boolean;
  lockedSpaceName?: string | null;
  spaces: Space[];
  selectedSpaces: string[];
  onToggleSpace: (id: string) => void;
  onSelectAllSpaces: () => void;
  onNewChat: () => void;
  newChatDisabled?: boolean;
  conversations: AskConversation[];
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onRenameConversation: (id: string, title: string) => void;
  onDeleteConversation: (id: string) => void;
  mode: string | null;
}) {
  if (collapsed) {
    return (
      <aside className="flex w-12 shrink-0 flex-col items-center border-r border-border bg-surface py-3">
        <button type="button" className="icon-button" onClick={onToggleCollapsed} title="Expand sidebar">
          <PanelLeft size={18} />
        </button>
      </aside>
    );
  }

  return (
    <aside className="flex w-full shrink-0 flex-col border-r border-border bg-surface lg:w-[300px]">
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-3">
        <div className="flex items-center gap-2">
          <AiBrandIcon size={20} className="text-primary" />
          <span className="text-sm font-semibold text-foreground">{askAI.title}</span>
        </div>
        <button type="button" className="icon-button" onClick={onToggleCollapsed} title="Collapse sidebar">
          <ChevronLeft size={18} />
        </button>
      </div>

      <div className="space-y-3 border-b border-border px-3 py-3">
        {lockScope ? (
          <div className="rounded-xl border border-border bg-surface-muted/40 px-3 py-2.5">
            <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
              {askAI.spaceScopeLabel}
            </p>
            <p className="mt-1 truncate text-sm font-semibold text-foreground">
              {lockedSpaceName || spaces[0]?.name || "Space"}
            </p>
            <p className="mt-0.5 text-[11px] text-muted">{askAI.spaceScopeHint}</p>
          </div>
        ) : (
          <>
            <WorkspaceSelector
              workspaces={workspaces}
              value={workspaceId}
              onChange={onWorkspaceChange}
              locked={workspaceLocked}
            />
            <SpaceScopeSelector
              spaces={spaces}
              selected={selectedSpaces}
              onToggle={onToggleSpace}
              onSelectAll={onSelectAllSpaces}
            />
          </>
        )}
        <NewChatButton onClick={onNewChat} disabled={newChatDisabled} />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2 py-3">
        <ConversationList
          conversations={conversations}
          activeId={activeConversationId}
          onSelect={onSelectConversation}
          onRename={onRenameConversation}
          onDelete={onDeleteConversation}
        />
      </div>

      <div className="border-t border-border px-3 py-3">
        <div className="rounded-xl border border-border bg-surface-muted/50 px-3 py-2.5">
          <p className="text-xs font-semibold text-foreground">
            <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-emerald-500" />
            {mode === "GEMINI" ? askAI.geminiConnected : askAI.modeLibraryQa}
          </p>
          <p className="mt-1 text-[11px] leading-relaxed text-muted">{askAI.modeHint}</p>
        </div>
      </div>
    </aside>
  );
}
