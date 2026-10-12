"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
  AIResponseCard,
  AskAIEmptyState,
  AskAIErrorState,
  AskAIHeader,
  AskAISidebar,
  ChatComposer,
  StreamingIndicator,
  askAI,
} from "@/components/ask-ai";
import { UserQuestionBubble } from "@/components/ask-ai/UserQuestionBubble";
import {
  clientApi,
  csrfToken,
  type Space,
  type SpaceListResponse,
  type Workspace,
} from "@/lib/api";
import {
  postMessageSse,
  type AskConversation,
  type AskMessage,
  type AskStructured,
  type AskStreamMeta,
} from "@/lib/ask-ai";

type AiCred = {
  provider: string;
  status: string;
  key_mask: string | null;
  mode: string;
  last_validated_at: string | null;
};

export type AskAIWorkspaceProps = {
  initialWorkspaceId?: string;
  initialSpaceId?: string;
  /** Fit inside Space shell (no page negative margins). */
  embedded?: boolean;
  /** Lock to one workspace + one space; hide scope pickers. */
  lockScope?: boolean;
  /** Sync query string on /app/ask. Disabled when embedded. */
  syncUrl?: boolean;
};

export function AskAIWorkspace({
  initialWorkspaceId = "",
  initialSpaceId,
  embedded = false,
  lockScope = false,
  syncUrl: syncUrlEnabled,
}: AskAIWorkspaceProps) {
  const allowUrlSync = syncUrlEnabled ?? !embedded;
  const client = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);
  const abortRef = useRef<AbortController | null>(null);

  const { data: workspaces = [] } = useQuery({
    queryKey: ["workspaces", "ask"],
    queryFn: () => clientApi<Workspace[]>("/workspaces?filter=all"),
  });

  const [workspaceId, setWorkspaceId] = useState<string>(
    initialWorkspaceId || (allowUrlSync ? searchParams.get("workspaceId") || "" : ""),
  );
  const effectiveWs = workspaceId || workspaces[0]?.id || "";

  const { data: spacesData } = useQuery({
    queryKey: ["spaces", "ask", effectiveWs],
    queryFn: () =>
      clientApi<SpaceListResponse>(`/workspaces/${effectiveWs}/spaces?tab=all&page_size=100`),
    enabled: !!effectiveWs,
  });
  const spaces: Space[] = useMemo(() => {
    const items = spacesData?.items ?? [];
    if (lockScope && initialSpaceId) {
      return items.filter((s) => s.id === initialSpaceId);
    }
    return items;
  }, [spacesData?.items, lockScope, initialSpaceId]);

  const lockedSpace = lockScope
    ? spaces[0] || spacesData?.items?.find((s) => s.id === initialSpaceId)
    : null;

  const { data: cred } = useQuery({
    queryKey: ["ai-credentials"],
    queryFn: () => clientApi<AiCred>("/me/ai-credentials"),
  });

  const [selectedSpaces, setSelectedSpaces] = useState<string[]>(() => {
    if (initialSpaceId) return [initialSpaceId];
    if (allowUrlSync) {
      const sid = searchParams.get("spaceId");
      return sid ? [sid] : [];
    }
    return [];
  });

  const [conversationId, setConversationId] = useState<string | null>(
    allowUrlSync ? searchParams.get("conversationId") : null,
  );
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState("");
  const [streamStructured, setStreamStructured] = useState<AskStructured | null>(null);
  const [streamMeta, setStreamMeta] = useState<AskStreamMeta>({});
  const [streamCitations, setStreamCitations] = useState<AskMessage["citations"]>([]);
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [quotaError, setQuotaError] = useState(false);
  const [geminiError, setGeminiError] = useState(false);
  const [showJump, setShowJump] = useState(false);

  const geminiConnected = cred?.status === "CONNECTED" && cred?.mode === "GEMINI";

  useEffect(() => {
    if (lockScope && initialSpaceId) {
      setSelectedSpaces([initialSpaceId]);
    }
  }, [lockScope, initialSpaceId]);

  useEffect(() => {
    if (initialWorkspaceId) setWorkspaceId(initialWorkspaceId);
  }, [initialWorkspaceId]);

  const { data: conversations = [] } = useQuery({
    queryKey: ["conversations", effectiveWs],
    queryFn: () => clientApi<AskConversation[]>(`/workspaces/${effectiveWs}/conversations`),
    enabled: !!effectiveWs,
  });

  const scopedConversations = useMemo(() => {
    if (!lockScope || !initialSpaceId) return conversations;
    return conversations.filter((c) => (c.space_ids || []).includes(initialSpaceId));
  }, [conversations, lockScope, initialSpaceId]);

  const { data: messages = [], refetch: refetchMessages } = useQuery({
    queryKey: ["messages", conversationId],
    queryFn: () => clientApi<AskMessage[]>(`/conversations/${conversationId}/messages`),
    enabled: !!conversationId,
  });

  const syncUrl = (next: {
    workspaceId?: string;
    conversationId?: string | null;
    spaceId?: string;
  }) => {
    if (!allowUrlSync) return;
    const params = new URLSearchParams(searchParams.toString());
    const ws = next.workspaceId ?? effectiveWs;
    if (ws) params.set("workspaceId", ws);
    if (next.conversationId) params.set("conversationId", next.conversationId);
    else if (next.conversationId === null) params.delete("conversationId");
    if (next.spaceId) params.set("spaceId", next.spaceId);
    router.replace(`/app/ask?${params.toString()}`, { scroll: false });
  };

  useEffect(() => {
    if (lockScope || !allowUrlSync) return;
    const sid = searchParams.get("spaceId");
    if (!sid) return;
    setSelectedSpaces((prev) => (prev.includes(sid) ? prev : [...prev, sid]));
  }, [searchParams, lockScope, allowUrlSync]);

  useEffect(() => {
    if (lockScope) return;
    if (!selectedSpaces.length && spaces.length === 1) {
      setSelectedSpaces([spaces[0].id]);
    }
  }, [spaces, selectedSpaces.length, lockScope]);

  useEffect(() => {
    if (cred?.mode) setMode(cred.mode);
  }, [cred?.mode]);

  const createConv = useMutation({
    mutationFn: (spaceIds: string[]) =>
      clientApi<AskConversation>(`/workspaces/${effectiveWs}/conversations`, {
        method: "POST",
        body: JSON.stringify({ space_ids: spaceIds }),
      }),
    onSuccess: (c) => {
      setConversationId(c.id);
      syncUrl({ conversationId: c.id });
      client.invalidateQueries({ queryKey: ["conversations", effectiveWs] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const toggleSpace = (id: string) => {
    if (lockScope) return;
    setSelectedSpaces((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    stickToBottom.current = atBottom;
    setShowJump(!atBottom);
  };

  useEffect(() => {
    if (!stickToBottom.current) return;
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, streaming, streamStructured, pendingUser]);

  const stop = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setBusy(false);
  };

  const send = async (override?: string) => {
    const q = (override ?? input).trim();
    if (!q || busy) return;
    if (!geminiConnected) {
      setGeminiError(true);
      toast.error(askAI.connectTitle);
      return;
    }
    if (!effectiveWs) {
      toast.error("Select a workspace");
      return;
    }
    const scopeIds =
      lockScope && initialSpaceId
        ? [initialSpaceId]
        : selectedSpaces.length > 0
          ? selectedSpaces
          : spaces.slice(0, 1).map((s) => s.id);
    if (!scopeIds.length) {
      toast.error(askAI.noSpace);
      return;
    }

    setBusy(true);
    setQuotaError(false);
    setGeminiError(false);
    setStreaming("");
    setStreamStructured(null);
    setStreamMeta({});
    setStreamCitations([]);
    setPendingUser(q);
    if (!override) setInput("");
    stickToBottom.current = true;

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      let cid = conversationId;
      if (!cid) {
        const c = await clientApi<AskConversation>(`/workspaces/${effectiveWs}/conversations`, {
          method: "POST",
          body: JSON.stringify({ space_ids: scopeIds }),
        });
        cid = c.id;
        setConversationId(c.id);
        syncUrl({ conversationId: c.id });
        client.invalidateQueries({ queryKey: ["conversations", effectiveWs] });
      }

      const result = await postMessageSse(cid, q, {
        spaceIds: scopeIds,
        csrf: csrfToken(),
        signal: controller.signal,
        onToken: (t) => setStreaming((s) => s + t),
        onMeta: (m) => {
          setStreamMeta(m);
          if (m.mode) setMode(m.mode);
        },
        onStructured: (s) => setStreamStructured(s),
      });
      setMode(result.mode);
      setStreamCitations(result.citations);
      setStreaming("");
      setStreamStructured(null);
      setPendingUser(null);
      await refetchMessages();
      client.invalidateQueries({ queryKey: ["conversations", effectiveWs] });
    } catch (e) {
      if ((e as Error).name === "AbortError") {
        setPendingUser(null);
        setStreaming("");
        return;
      }
      const err = e as Error & { status?: number; code?: string };
      if (err.status === 429 || err.code === "GEMINI_QUOTA") {
        setQuotaError(true);
      } else if (err.status === 403 || err.code === "GEMINI_NOT_CONNECTED") {
        setGeminiError(true);
        client.invalidateQueries({ queryKey: ["ai-credentials"] });
      } else if (err.status === 502 || err.code === "GEMINI_MODEL_UNAVAILABLE") {
        toast.error(
          err.message || "Gemini model unavailable. Re-save your API key in Settings → AI.",
        );
        client.invalidateQueries({ queryKey: ["ai-credentials"] });
      } else if (
        err.code === "INTERNAL_ERROR" &&
        /gemini http 404/i.test(err.message || "")
      ) {
        toast.error(
          "Ask AI is using an outdated API server or saved key. Open Settings → AI, paste your key, Test, then Save & connect.",
        );
        client.invalidateQueries({ queryKey: ["ai-credentials"] });
      } else {
        toast.error(err.message || "Ask failed");
      }
      setPendingUser(null);
      setStreaming("");
    } finally {
      abortRef.current = null;
      setBusy(false);
    }
  };

  const regenerate = () => {
    const lastUser = [...messages].reverse().find((m) => m.role === "USER");
    if (lastUser) void send(lastUser.content);
  };

  const workspaceLocked = Boolean(lockScope || (conversationId && messages.length > 0));
  const fallbackSpaceId = lockScope
    ? initialSpaceId
    : selectedSpaces[0] || spaces[0]?.id;

  const pairs = useMemo(() => {
    const out: { user?: AskMessage; assistant?: AskMessage }[] = [];
    for (const m of messages) {
      if (m.role === "USER") out.push({ user: m });
      else if (m.role === "ASSISTANT") {
        const last = out[out.length - 1];
        if (last && !last.assistant) last.assistant = m;
        else out.push({ assistant: m });
      }
    }
    return out;
  }, [messages]);

  const shellClass = embedded
    ? "flex h-full min-h-0 flex-col bg-background lg:flex-row"
    : "absolute inset-0 flex min-h-0 flex-col bg-background lg:flex-row";

  return (
    <div className={shellClass}>
      <div
        className={`${
          sidebarCollapsed
            ? ""
            : "max-lg:absolute max-lg:inset-y-0 max-lg:left-0 max-lg:z-30 max-lg:shadow-xl"
        } flex h-full`}
      >
        <AskAISidebar
          collapsed={sidebarCollapsed}
          onToggleCollapsed={() => setSidebarCollapsed((v) => !v)}
          workspaces={workspaces}
          workspaceId={effectiveWs}
          onWorkspaceChange={(id) => {
            if (lockScope) return;
            setWorkspaceId(id);
            setConversationId(null);
            setSelectedSpaces([]);
            syncUrl({ workspaceId: id, conversationId: null });
          }}
          workspaceLocked={workspaceLocked}
          lockScope={lockScope}
          lockedSpaceName={lockedSpace?.name}
          spaces={spaces}
          selectedSpaces={selectedSpaces}
          onToggleSpace={toggleSpace}
          onSelectAllSpaces={() => {
            if (lockScope) return;
            setSelectedSpaces(spaces.map((s) => s.id));
          }}
          onNewChat={() => {
            setConversationId(null);
            setPendingUser(null);
            setStreaming("");
            syncUrl({ conversationId: null });
            const scope =
              lockScope && initialSpaceId
                ? [initialSpaceId]
                : selectedSpaces;
            if (scope.length) createConv.mutate(scope);
          }}
          newChatDisabled={
            !effectiveWs ||
            createConv.isPending ||
            !(lockScope ? initialSpaceId : selectedSpaces.length)
          }
          conversations={scopedConversations}
          activeConversationId={conversationId}
          onSelectConversation={(id) => {
            setConversationId(id);
            syncUrl({ conversationId: id });
            if (!lockScope) {
              const conv = conversations.find((c) => c.id === id);
              if (conv?.space_ids?.length) setSelectedSpaces(conv.space_ids);
            }
          }}
          onRenameConversation={async (id, title) => {
            try {
              await clientApi(`/conversations/${id}`, {
                method: "PATCH",
                body: JSON.stringify({ title }),
              });
              client.invalidateQueries({ queryKey: ["conversations", effectiveWs] });
            } catch (e) {
              toast.error(e instanceof Error ? e.message : "Rename failed");
            }
          }}
          onDeleteConversation={async (id) => {
            try {
              await clientApi(`/conversations/${id}`, { method: "DELETE" });
              if (conversationId === id) {
                setConversationId(null);
                syncUrl({ conversationId: null });
              }
              client.invalidateQueries({ queryKey: ["conversations", effectiveWs] });
            } catch (e) {
              toast.error(e instanceof Error ? e.message : "Delete failed");
            }
          }}
          mode={mode || cred?.mode || null}
        />
      </div>

      <section className="relative flex min-w-0 flex-1 flex-col bg-background">
        <AskAIHeader
          onPickPrompt={(p) => setInput(p)}
          title={lockScope ? askAI.spacePageTitle : askAI.pageTitle}
          subtitle={
            lockScope
              ? askAI.spacePageSubtitle.replace(
                  "{space}",
                  lockedSpace?.name || "this Space",
                )
              : askAI.pageSubtitle
          }
        />

        <div
          ref={scrollRef}
          onScroll={onScroll}
          className="min-h-0 flex-1 overflow-y-auto px-4 pb-4 pt-4 sm:px-6"
        >
          <div className={embedded ? "mx-auto max-w-4xl space-y-6" : "page-shell space-y-6"}>
            {quotaError ? (
              <AskAIErrorState
                title={askAI.quotaTitle}
                body={askAI.quotaBody}
                actionLabel={askAI.aiSettings}
                actionHref="/app/settings/ai"
              />
            ) : null}

            {geminiError || (!geminiConnected && cred) ? (
              <AskAIErrorState
                title={askAI.connectTitle}
                body="Connect your Gemini API key in AI Settings before asking questions."
                actionLabel={askAI.connectGemini}
                actionHref="/app/settings/ai"
              />
            ) : null}

            {!messages.length && !pendingUser && !streaming && !quotaError && geminiConnected ? (
              <AskAIEmptyState
                onPick={(p) => {
                  setInput(p);
                }}
              />
            ) : null}

            {pairs.map((pair, idx) => (
              <div key={pair.user?.id || pair.assistant?.id || idx} className="space-y-3">
                {pair.user ? <UserQuestionBubble content={pair.user.content} /> : null}
                {pair.assistant ? (
                  <AIResponseCard
                    content={pair.assistant.content}
                    structured={pair.assistant.structured}
                    citations={pair.assistant.citations || []}
                    workspaceId={effectiveWs}
                    fallbackSpaceId={fallbackSpaceId}
                    chunkCount={pair.assistant.retrieved_chunk_count}
                    docCount={pair.assistant.unique_document_count}
                    onRegenerate={idx === pairs.length - 1 ? regenerate : undefined}
                  />
                ) : null}
              </div>
            ))}

            {pendingUser ? (
              <div className="space-y-3">
                <UserQuestionBubble content={pendingUser} />
                {busy ? <StreamingIndicator /> : null}
                <AIResponseCard
                  content={streaming}
                  structured={streamStructured}
                  citations={streamCitations}
                  workspaceId={effectiveWs}
                  fallbackSpaceId={fallbackSpaceId}
                  chunkCount={streamMeta.retrieved_chunk_count}
                  docCount={streamMeta.unique_document_count}
                  streaming={busy}
                />
              </div>
            ) : null}
          </div>
        </div>

        {showJump ? (
          <button
            type="button"
            className="absolute bottom-28 left-1/2 z-10 -translate-x-1/2 rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium shadow"
            onClick={() => {
              stickToBottom.current = true;
              const el = scrollRef.current;
              if (el) el.scrollTop = el.scrollHeight;
              setShowJump(false);
            }}
          >
            {askAI.jumpToLatest}
          </button>
        ) : null}

        <ChatComposer
          value={input}
          onChange={setInput}
          onSend={() => void send()}
          onStop={stop}
          busy={busy}
          noSpace={!selectedSpaces.length && spaces.length > 0 && !lockScope}
          disabled={!effectiveWs || !geminiConnected || (lockScope && !initialSpaceId)}
        />
      </section>
    </div>
  );
}
