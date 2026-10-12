"use client";

export function CancelImportDialog({
  open,
  onKeep,
  onConfirm,
  pending,
  force,
}: {
  open: boolean;
  onKeep: () => void;
  onConfirm: () => void;
  pending?: boolean;
  force?: boolean;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
      <section className="w-full max-w-md rounded-2xl border border-border bg-surface p-5 shadow-2xl">
        <h3 className="text-lg font-semibold">
          {force ? "Force stop import?" : "Cancel import?"}
        </h3>
        <p className="mt-2 text-sm text-muted">
          Stop this import now. Pages already downloaded stay in the Space. The worker will exit as
          soon as it can.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onKeep} disabled={pending}>
            Keep importing
          </button>
          <button type="button" className="danger-button" onClick={onConfirm} disabled={pending}>
            {force ? "Force stop" : "Cancel import"}
          </button>
        </div>
      </section>
    </div>
  );
}
