/** Bright cosmic knowledge universe. Decorative only — no labels. */
export function KnowledgeHeroVisual() {
  return (
    <div className="welcome-viz" aria-hidden="true">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/brand/welcome/knowledge-network-light.webp?v=2"
        alt=""
        width={1536}
        height={1024}
        className="welcome-viz-img"
        decoding="async"
        fetchPriority="high"
      />
    </div>
  );
}
