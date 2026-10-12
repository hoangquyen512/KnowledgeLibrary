"use client";

import { useRef, useState } from "react";
import { CalendarDays } from "lucide-react";
import { formatRangeLabel } from "@/lib/admin-format";
import { useClickOutside } from "@/lib/use-click-outside";

export function AdminDateRangePicker({
  from,
  to,
  onChange,
}: {
  from: string;
  to: string;
  onChange: (next: { from: string; to: string }) => void;
}) {
  const [open, setOpen] = useState(false);
  const [draftFrom, setDraftFrom] = useState(from);
  const [draftTo, setDraftTo] = useState(to);
  const wrapRef = useRef<HTMLDivElement>(null);
  useClickOutside(wrapRef, open, () => setOpen(false));

  return (
    <div className="relative" ref={wrapRef}>
      <button
        type="button"
        className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface px-3 py-2 text-sm font-medium text-foreground shadow-sm hover:bg-surface-muted"
        onClick={() => {
          setDraftFrom(from);
          setDraftTo(to);
          setOpen((v) => !v);
        }}
        aria-expanded={open}
      >
        <CalendarDays size={16} className="text-muted" />
        {formatRangeLabel(from, to)}
      </button>
      {open ? (
        <div className="absolute right-0 z-20 mt-2 w-72 rounded-2xl border border-border bg-surface p-3 shadow-lg">
          <div className="grid gap-2">
            <label className="text-xs font-medium text-muted">
              From
              <input
                type="date"
                className="input mt-1"
                value={draftFrom}
                max={draftTo}
                onChange={(e) => setDraftFrom(e.target.value)}
              />
            </label>
            <label className="text-xs font-medium text-muted">
              To
              <input
                type="date"
                className="input mt-1"
                value={draftTo}
                min={draftFrom}
                onChange={(e) => setDraftTo(e.target.value)}
              />
            </label>
          </div>
          <div className="mt-3 flex justify-end gap-2">
            <button type="button" className="secondary-button px-3 py-1.5 text-xs" onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button
              type="button"
              className="primary-button px-3 py-1.5 text-xs"
              onClick={() => {
                onChange({ from: draftFrom, to: draftTo < draftFrom ? draftFrom : draftTo });
                setOpen(false);
              }}
            >
              Apply
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
