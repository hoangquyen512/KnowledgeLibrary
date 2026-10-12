import { BrandMascot } from "./BrandMascot";

type BrandLoadingProps = {
  label?: string;
  className?: string;
};

export function BrandLoading({ label = "Loading…", className = "" }: BrandLoadingProps) {
  return (
    <div
      className={`grid min-h-48 place-items-center rounded-2xl border border-border bg-surface p-6 ${className}`}
      role="status"
      aria-live="polite"
    >
      <div className="flex flex-col items-center gap-3">
        <BrandMascot mood="loading" size={72} className="brand-loading-mascot h-[72px] w-[72px]" />
        <p className="text-sm text-muted">{label}</p>
      </div>
    </div>
  );
}
