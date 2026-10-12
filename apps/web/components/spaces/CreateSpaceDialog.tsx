"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BarChart3,
  BookOpen,
  Briefcase,
  Code2,
  FileText,
  Folder,
  Globe,
  LoaderCircle,
  Megaphone,
  Shield,
  Users,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useAppRouter } from "@/components/navigation-progress";
import { toast } from "sonner";
import { clientApi, type Space, type Workspace } from "@/lib/api";

const ICONS = {
  folder: Folder,
  book: BookOpen,
  users: Users,
  chart: BarChart3,
  code: Code2,
  megaphone: Megaphone,
  shield: Shield,
  globe: Globe,
  briefcase: Briefcase,
  "file-text": FileText,
} as const;

const ACCENTS = ["blue", "green", "violet", "amber", "rose", "cyan", "slate"] as const;

function SpaceIcon({ iconKey, accent }: { iconKey: string; accent: string }) {
  const Icon = ICONS[iconKey as keyof typeof ICONS] || Folder;
  const tone =
    accent === "cyan" || accent === "slate" ? "blue" : accent;
  return (
    <span className={`stat-icon stat-${tone}`}>
      <Icon size={16} />
    </span>
  );
}

export function CreateSpaceDialog({
  open,
  onClose,
  workspaceId,
}: {
  open: boolean;
  onClose: () => void;
  workspaceId?: string | null;
}) {
  const client = useQueryClient();
  const router = useAppRouter();
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState(workspaceId || "");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [iconKey, setIconKey] = useState("folder");
  const [accentKey, setAccentKey] = useState("blue");

  const { data: workspaces = [] } = useQuery({
    queryKey: ["workspaces", "create-space"],
    queryFn: () => clientApi<Workspace[]>("/workspaces?filter=all"),
    enabled: open && !workspaceId,
  });

  useEffect(() => {
    if (workspaceId) setSelectedWorkspaceId(workspaceId);
  }, [workspaceId]);

  const targetId = workspaceId || selectedWorkspaceId;

  const mutation = useMutation({
    mutationFn: () =>
      clientApi<Space>(`/workspaces/${targetId}/spaces`, {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
          icon_key: iconKey,
          accent_key: accentKey,
        }),
      }),
    onSuccess: (space) => {
      client.invalidateQueries({ queryKey: ["spaces", targetId] });
      client.invalidateQueries({ queryKey: ["spaces", "sidebar", targetId] });
      client.invalidateQueries({ queryKey: ["workspace-overview", targetId] });
      client.invalidateQueries({ queryKey: ["dashboard"] });
      client.invalidateQueries({ queryKey: ["recent-spaces"] });
      toast.success("Space created");
      setName("");
      setDescription("");
      onClose();
      router.push(`/app/workspaces/${space.workspace_id}/spaces/${space.id}/pages`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
      <section className="w-full max-w-md rounded-2xl border border-border bg-surface p-5 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Create Space</h2>
          <button type="button" className="icon-button" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {!workspaceId ? (
          <label className="label mb-3 block">
            Workspace *
            <select
              className="input mt-1.5"
              value={selectedWorkspaceId}
              onChange={(e) => setSelectedWorkspaceId(e.target.value)}
            >
              <option value="">Select a workspace</option>
              {workspaces.map((ws) => (
                <option key={ws.id} value={ws.id}>
                  {ws.name}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        <label className="label">
          Space name *
          <input
            className="input mt-1.5"
            value={name}
            maxLength={100}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. DMS - Company Knowledge"
          />
        </label>
        <label className="label mt-3">
          Description
          <textarea
            className="input mt-1.5 resize-none"
            rows={3}
            maxLength={500}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <p className="label mt-3">Icon</p>
        <div className="mt-1.5 flex flex-wrap gap-2">
          {Object.keys(ICONS).map((key) => (
            <button
              key={key}
              type="button"
              className={`rounded-lg border p-2 ${iconKey === key ? "border-primary" : "border-border"}`}
              onClick={() => setIconKey(key)}
            >
              <SpaceIcon iconKey={key} accent={accentKey} />
            </button>
          ))}
        </div>
        <p className="label mt-3">Color</p>
        <div className="mt-1.5 flex flex-wrap gap-2">
          {ACCENTS.map((a) => (
            <button
              key={a}
              type="button"
              className={`h-7 w-7 rounded-full border ${accentKey === a ? "border-primary ring-2 ring-primary/30" : "border-border"}`}
              style={{ background: `var(--accent-${a}, #93c5fd)` }}
              onClick={() => setAccentKey(a)}
              aria-label={a}
            />
          ))}
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={!name.trim() || !targetId || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? <LoaderCircle className="animate-spin" size={16} /> : null}
            Create Space
          </button>
        </div>
      </section>
    </div>
  );
}
