"use client";

/** Decorative preview shown before generation completes. */
export function StudioMindmapPlaceholder({ centerLabel }: { centerLabel: string }) {
  const center = centerLabel.trim() || "Selected topic";

  const branches = [
    {
      color: "#3b82f6",
      label: "Overview",
      items: ["Goals", "Scope", "Stakeholders"],
      angle: -70,
    },
    {
      color: "#ec4899",
      label: "Features",
      items: ["API integration", "Order management", "Reports"],
      angle: -20,
    },
    {
      color: "#f97316",
      label: "Documents",
      items: ["Requirements", "User guides", "Specs"],
      angle: 30,
    },
    {
      color: "#eab308",
      label: "Next steps",
      items: ["Short term", "Medium term", "Risks"],
      angle: 80,
    },
    {
      color: "#14b8a6",
      label: "Key changes",
      items: ["Price sync", "Onboarding", "UI updates"],
      angle: 140,
    },
  ] as const;

  const cx = 400;
  const cy = 260;
  const r1 = 110;
  const r2 = 190;

  return (
    <svg viewBox="0 0 800 520" className="h-full w-full" aria-hidden>
      <defs>
        <filter id="mm-shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="1" stdDeviation="2" floodOpacity="0.12" />
        </filter>
      </defs>
      {branches.map((b) => {
        const rad = (b.angle * Math.PI) / 180;
        const bx = cx + Math.cos(rad) * r1;
        const by = cy + Math.sin(rad) * r1;
        const ex = cx + Math.cos(rad) * r2;
        const ey = cy + Math.sin(rad) * r2;
        return (
          <g key={b.label}>
            <line x1={cx} y1={cy} x2={bx} y2={by} stroke={b.color} strokeWidth={2.5} opacity={0.85} />
            <line x1={bx} y1={by} x2={ex} y2={ey} stroke={b.color} strokeWidth={2} opacity={0.55} />
            <rect
              x={bx - 52}
              y={by - 14}
              width={104}
              height={28}
              rx={8}
              fill={b.color}
              opacity={0.92}
              filter="url(#mm-shadow)"
            />
            <text
              x={bx}
              y={by + 4}
              textAnchor="middle"
              fill="white"
              fontSize={11}
              fontWeight={600}
            >
              {b.label}
            </text>
            {b.items.map((item, i) => {
              const spread = (i - 1) * 22;
              const nx = ex + Math.cos(rad) * 36;
              const ny = ey + spread;
              return (
                <g key={item}>
                  <line x1={ex} y1={ey} x2={nx} y2={ny} stroke={b.color} strokeWidth={1.5} opacity={0.45} />
                  <rect
                    x={nx - 44}
                    y={ny - 11}
                    width={88}
                    height={22}
                    rx={6}
                    fill="white"
                    stroke={b.color}
                    strokeWidth={1}
                    opacity={0.95}
                  />
                  <text x={nx} y={ny + 4} textAnchor="middle" fill="#334155" fontSize={9}>
                    {item}
                  </text>
                </g>
              );
            })}
          </g>
        );
      })}
      <rect
        x={cx - 90}
        y={cy - 22}
        width={180}
        height={44}
        rx={10}
        fill="white"
        stroke="#cbd5e1"
        strokeWidth={1.5}
        filter="url(#mm-shadow)"
      />
      <text x={cx} y={cy + 5} textAnchor="middle" fill="#0f172a" fontSize={12} fontWeight={700}>
        {center.length > 28 ? `${center.slice(0, 26)}…` : center}
      </text>
    </svg>
  );
}

export function StudioPresentationPlaceholder({ title }: { title: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 p-8">
      <div className="w-full max-w-md rounded-2xl border border-border bg-surface shadow-sm">
        <div className="border-b border-border px-5 py-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted">Slide 1</p>
          <h3 className="mt-1 text-base font-semibold text-foreground">
            {title.trim() || "Your presentation title"}
          </h3>
        </div>
        <ul className="space-y-2 px-5 py-4 text-sm text-muted">
          <li className="flex gap-2">
            <span className="text-primary">•</span>
            <span>Key insight from selected Spaces</span>
          </li>
          <li className="flex gap-2">
            <span className="text-primary">•</span>
            <span>Supporting detail with citations</span>
          </li>
          <li className="flex gap-2">
            <span className="text-primary">•</span>
            <span>Summary and next steps</span>
          </li>
        </ul>
      </div>
      <div className="flex gap-2">
        {[2, 3].map((n) => (
          <div
            key={n}
            className="h-16 w-24 rounded-lg border border-dashed border-border bg-surface-muted/60"
          />
        ))}
      </div>
    </div>
  );
}
