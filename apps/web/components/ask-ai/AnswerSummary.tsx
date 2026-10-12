"use client";

import { toPlainText } from "@/lib/ask-ai";

export function AnswerSummary({ items }: { items: string[] }) {
  const plain = items
    .map((item) => toPlainText(item).replace(/\s*\[\d+\]\s*/g, " ").trim())
    .filter(Boolean);
  if (!plain.length) return null;
  return (
    <section>
      <h3 className="mb-2.5 flex items-center gap-2 text-[15px] font-semibold text-foreground">
        <span className="text-base" aria-hidden>
          📚
        </span>
        Quick summary
      </h3>
      <ul className="space-y-2.5 text-[14px] leading-[1.65] text-foreground/90">
        {plain.map((item, i) => (
          <li key={i} className="flex gap-2.5">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
            <span className="min-w-0 flex-1 break-words">{item}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
