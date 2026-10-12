"use client";

import { AlertTriangle, Check, Clock, FileText, Loader2, Minus } from "lucide-react";

export function CurrentImportItems({
  items,
}: {
  items: { name: string; status: string; type?: string }[];
}) {
  if (!items.length) {
    return <p className="text-sm text-muted">Waiting for items…</p>;
  }
  return (
    <ul className="space-y-2.5">
      {items.slice(0, 8).map((item, idx) => (
        <li key={`${item.name}-${idx}`} className="flex items-center gap-2 text-sm">
          <FileText size={14} className="shrink-0 text-muted" aria-hidden />
          <span className="min-w-0 flex-1 truncate font-medium">{item.name}</span>
          <ItemStatus status={item.status} />
        </li>
      ))}
    </ul>
  );
}

function ItemStatus({ status }: { status: string }) {
  if (status === "imported") {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-emerald-700 dark:text-emerald-300">
        <Check size={12} /> Imported
      </span>
    );
  }
  if (status === "importing") {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-primary">
        <Loader2 size={12} className="animate-spin" /> Importing…
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-rose-600">
        <AlertTriangle size={12} /> Failed
      </span>
    );
  }
  if (status === "skipped") {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted">
        <Minus size={12} /> Skipped
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted">
      <Clock size={12} /> Queued
    </span>
  );
}
