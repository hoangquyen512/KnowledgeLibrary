/** Decorative abstract backdrop — brand palette, non-figurative. */
export function LoginAbstractArt() {
  return (
    <svg
      className="login-screen-art"
      viewBox="0 0 1200 800"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      preserveAspectRatio="xMidYMid slice"
    >
      <defs>
        <linearGradient id="loginRibbonA" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#2F5BEA" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#6C3EF0" stopOpacity="0.2" />
        </linearGradient>
        <linearGradient id="loginRibbonB" x1="1" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#4B4FE8" stopOpacity="0.45" />
          <stop offset="100%" stopColor="#102A6A" stopOpacity="0.12" />
        </linearGradient>
        <linearGradient id="loginOrb" x1="0.2" y1="0" x2="0.8" y2="1">
          <stop offset="0%" stopColor="#D9D5FF" stopOpacity="0.85" />
          <stop offset="100%" stopColor="#2F5BEA" stopOpacity="0.15" />
        </linearGradient>
        <radialGradient id="loginGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#6C3EF0" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#6C3EF0" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Soft orbs */}
      <circle cx="980" cy="140" r="180" fill="url(#loginGlow)" />
      <circle cx="160" cy="620" r="220" fill="url(#loginGlow)" opacity="0.7" />
      <circle cx="980" cy="620" r="90" fill="url(#loginOrb)" opacity="0.55" />
      <circle cx="210" cy="160" r="54" fill="#2F5BEA" opacity="0.12" />
      <circle cx="250" cy="200" r="22" fill="#6C3EF0" opacity="0.2" />

      {/* Flowing ribbons */}
      <path
        d="M-40 420 C180 280 320 520 520 380 C720 240 860 460 1240 300"
        stroke="url(#loginRibbonA)"
        strokeWidth="72"
        strokeLinecap="round"
        opacity="0.55"
      />
      <path
        d="M-60 540 C200 400 380 640 580 500 C780 360 940 580 1260 440"
        stroke="url(#loginRibbonB)"
        strokeWidth="48"
        strokeLinecap="round"
        opacity="0.45"
      />

      {/* Geometric arcs / rings */}
      <circle cx="1040" cy="220" r="118" stroke="#4B4FE8" strokeWidth="1.5" opacity="0.35" />
      <circle cx="1040" cy="220" r="78" stroke="#6C3EF0" strokeWidth="1.25" opacity="0.28" strokeDasharray="6 10" />
      <circle cx="180" cy="560" r="96" stroke="#2F5BEA" strokeWidth="1.5" opacity="0.28" />

      {/* Abstract node constellation (knowledge graph hint) */}
      <g stroke="#102A6A" strokeWidth="1.25" opacity="0.22">
        <line x1="820" y1="120" x2="900" y2="180" />
        <line x1="900" y1="180" x2="960" y2="110" />
        <line x1="900" y1="180" x2="940" y2="250" />
        <line x1="140" y1="280" x2="220" y2="320" />
        <line x1="220" y1="320" x2="190" y2="390" />
      </g>
      <g fill="#2F5BEA" opacity="0.35">
        <circle cx="820" cy="120" r="4" />
        <circle cx="900" cy="180" r="5.5" />
        <circle cx="960" cy="110" r="3.5" />
        <circle cx="940" cy="250" r="4" />
        <circle cx="140" cy="280" r="3.5" />
        <circle cx="220" cy="320" r="5" />
        <circle cx="190" cy="390" r="3" />
      </g>

      {/* Thin diagonal accents */}
      <path
        d="M760 720 L1120 480"
        stroke="#6C3EF0"
        strokeWidth="2"
        opacity="0.18"
        strokeLinecap="round"
      />
      <path
        d="M70 120 L280 40"
        stroke="#102A6A"
        strokeWidth="2"
        opacity="0.14"
        strokeLinecap="round"
      />
    </svg>
  );
}
