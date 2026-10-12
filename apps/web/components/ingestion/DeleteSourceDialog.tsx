"use client";

export function DeleteSourceDialog({
  open,
  sourceName,
  pending,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  sourceName: string;
  pending?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
      <section className="w-full max-w-md rounded-2xl border border-border bg-surface p-5 shadow-2xl">
        <h3 className="text-lg font-semibold">Delete source?</h3>
        <p className="mt-2 text-sm text-muted">
          Delete <span className="font-medium text-foreground">{sourceName}</span>? This removes the
          Source and{" "}
          <span className="font-medium text-foreground">
            all imported pages, attachments, and diagrams
          </span>{" "}
          from this Space. This cannot be undone.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onCancel} disabled={pending}>
            Cancel
          </button>
          <button type="button" className="danger-button" onClick={onConfirm} disabled={pending}>
            Delete source
          </button>
        </div>
      </section>
    </div>
  );
}
