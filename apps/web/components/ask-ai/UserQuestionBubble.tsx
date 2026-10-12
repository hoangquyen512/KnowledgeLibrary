"use client";

export function UserQuestionBubble({ content }: { content: string }) {
  return (
    <div className="flex max-w-[80%] items-start gap-2.5">
      <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full bg-blue-100 text-xs font-semibold text-blue-700 dark:bg-blue-950 dark:text-blue-300">
        You
      </div>
      <div className="rounded-2xl bg-blue-50 px-3.5 py-2.5 text-[14px] leading-[1.55] text-foreground dark:bg-blue-950/35">
        {content}
      </div>
    </div>
  );
}
