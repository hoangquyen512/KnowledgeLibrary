"use client";

import { studio } from "./strings";

const STEPS = [
  { key: 1, label: studio.stepInput },
  { key: 2, label: studio.stepReview },
  { key: 3, label: studio.stepGenerate },
] as const;

export function StudioStepper({ current }: { current: 1 | 2 | 3 }) {
  return (
    <div className="shrink-0 border-b border-border px-3 py-2.5">
      <ol className="grid grid-cols-3 gap-1">
        {STEPS.map((step) => {
          const active = step.key === current;
          const done = step.key < current;
          return (
            <li
              key={step.key}
              className={`flex items-center justify-center gap-1.5 rounded-lg px-1.5 py-1.5 text-[11px] font-semibold ${
                active
                  ? "bg-blue-50 text-primary dark:bg-blue-950/40"
                  : done
                    ? "text-foreground"
                    : "text-muted"
              }`}
            >
              <span
                className={`grid h-5 w-5 shrink-0 place-items-center rounded-full text-[10px] ${
                  active
                    ? "bg-primary text-primary-foreground"
                    : done
                      ? "bg-primary/20 text-primary"
                      : "bg-surface-muted text-muted"
                }`}
              >
                {step.key}
              </span>
              <span className="truncate">{step.label}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
