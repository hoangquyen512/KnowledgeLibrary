import { BrandMascot } from "./BrandMascot";
import type { MascotMood } from "./tokens";

type BrandEmptyStateProps = {
  mood?: Extract<MascotMood, "full" | "search" | "empty">;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
};

export function BrandEmptyState({
  mood = "empty",
  title,
  description,
  action,
  className = "",
}: BrandEmptyStateProps) {
  return (
    <div className={`empty-state ${className}`}>
      <BrandMascot mood={mood} size={120} className="h-[120px] w-[120px] object-contain" />
      <h3 className="mt-4 text-base font-semibold text-foreground">{title}</h3>
      {description ? (
        <p className="mt-1 max-w-sm text-sm leading-6 text-muted">{description}</p>
      ) : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
