export function RouteSkeleton({ cards = 4 }: { cards?: number }) {
  return (
    <div className="route-skeleton" aria-busy="true" aria-live="polite">
      <div className="h-8 w-52 animate-pulse rounded-lg bg-surface-muted" />
      <div className="mt-3 h-4 w-72 max-w-full animate-pulse rounded bg-surface-muted" />
      <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: cards }).map((_, index) => (
          <div key={index} className="h-28 animate-pulse rounded-2xl bg-surface-muted" />
        ))}
      </div>
      <div className="mt-4 h-64 animate-pulse rounded-2xl bg-surface-muted" />
    </div>
  );
}
