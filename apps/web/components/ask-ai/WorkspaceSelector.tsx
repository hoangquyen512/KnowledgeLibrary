"use client";

import { ChevronDown } from "lucide-react";
import type { Workspace } from "@/lib/api";
import { askAI } from "./strings";

export function WorkspaceSelector({
  workspaces,
  value,
  onChange,
  locked,
}: {
  workspaces: Workspace[];
  value: string;
  onChange: (id: string) => void;
  locked?: boolean;
}) {
  return (
    <label className="block text-xs font-medium text-muted">
      {askAI.workspace}
      <div className="relative mt-1">
        <select
          className="input w-full appearance-none pr-8 text-sm font-medium"
          value={value}
          disabled={locked || workspaces.length === 0}
          onChange={(e) => onChange(e.target.value)}
          title={locked ? "Workspace is locked for this conversation" : undefined}
        >
          {workspaces.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>
        <ChevronDown size={14} className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-muted" />
      </div>
    </label>
  );
}
