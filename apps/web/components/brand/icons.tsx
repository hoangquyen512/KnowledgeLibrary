import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

const base = (size: number) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
});

/** Magnifier + 3 data points — Analyze */
export function AnalyzeIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size)} aria-hidden="true" {...props}>
      <circle cx="10" cy="10" r="6.25" />
      <path d="M15 15l5 5" />
      <circle cx="8" cy="9" r="1" fill="currentColor" stroke="none" />
      <circle cx="11.5" cy="7.5" r="1" fill="currentColor" stroke="none" />
      <circle cx="11" cy="12" r="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

/** Document corner + sparkle — Insights */
export function InsightsIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size)} aria-hidden="true" {...props}>
      <path d="M7 3.5h7l4 4V20a1.5 1.5 0 0 1-1.5 1.5H7A1.5 1.5 0 0 1 5.5 20V5A1.5 1.5 0 0 1 7 3.5Z" />
      <path d="M14 3.5V8h4.5" />
      <path d="M17.5 2.5l.4 1.1 1.1.4-1.1.4-.4 1.1-.4-1.1-1.1-.4 1.1-.4z" fill="currentColor" stroke="none" />
    </svg>
  );
}

/** Document + lines + sparkle — Summarize */
export function SummarizeIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size)} aria-hidden="true" {...props}>
      <path d="M6.5 3.5h8l3.5 3.5V20a1.5 1.5 0 0 1-1.5 1.5h-10A1.5 1.5 0 0 1 5 20V5A1.5 1.5 0 0 1 6.5 3.5Z" />
      <path d="M8.5 11h7M8.5 14.5h7M8.5 18h4.5" />
      <path d="M18.5 4l.35.95.95.35-.95.35L18.5 6.6l-.35-.95-.95-.35.95-.35z" fill="currentColor" stroke="none" />
    </svg>
  );
}

/** Two docs + center arrows — Compare */
export function CompareIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size)} aria-hidden="true" {...props}>
      <rect x="2.5" y="4" width="7.5" height="16" rx="1.25" />
      <rect x="14" y="4" width="7.5" height="16" rx="1.25" />
      <path d="M11 9h2M11 12h2M11 15h2" />
      <path d="M10.25 10.5 9 12l1.25 1.5M13.75 10.5 15 12l-1.25 1.5" />
    </svg>
  );
}

/** Ant-head mark + sparkle for AI chrome */
export function AiBrandIcon({ size = 20, className = "", ...props }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={className}
      {...props}
    >
      <defs>
        <linearGradient id="aiBrandGrad" x1="2" y1="2" x2="20" y2="22" gradientUnits="userSpaceOnUse">
          <stop stopColor="#2F5BEA" />
          <stop offset="1" stopColor="#6C3EF0" />
        </linearGradient>
      </defs>
      <ellipse cx="10" cy="13" rx="6.5" ry="6" fill="url(#aiBrandGrad)" />
      <ellipse cx="7.8" cy="12.5" rx="1.7" ry="2.1" fill="#F8FAFF" />
      <ellipse cx="12.2" cy="12.5" rx="1.7" ry="2.1" fill="#F8FAFF" />
      <circle cx="8.2" cy="13" r="0.85" fill="#0B1220" />
      <circle cx="12.6" cy="13" r="0.85" fill="#0B1220" />
      <path d="M7.5 7.5C6.8 5.2 5.5 4.2 4 4" stroke="url(#aiBrandGrad)" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="3.7" cy="3.7" r="1.1" fill="#6C3EF0" />
      <path d="M12.5 7.2c.9-2.2 2.4-3.2 4-3.4" stroke="url(#aiBrandGrad)" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="16.8" cy="3.5" r="1.1" fill="#2F5BEA" />
      <path
        d="M19.2 8.2l.45 1.2 1.2.45-1.2.45-.45 1.2-.45-1.2-1.2-.45 1.2-.45z"
        fill="#6C3EF0"
      />
    </svg>
  );
}
