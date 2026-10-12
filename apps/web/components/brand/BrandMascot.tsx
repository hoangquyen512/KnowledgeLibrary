import Image from "next/image";
import { BRAND, type MascotMood } from "./tokens";

const MOOD_SRC: Record<MascotMood, string> = {
  full: BRAND.paths.antFull,
  search: BRAND.paths.antSearch,
  empty: BRAND.paths.antEmpty,
  loading: BRAND.paths.antLoading,
  mark: BRAND.paths.antMark,
};

type BrandMascotProps = {
  mood?: MascotMood;
  size?: number;
  className?: string;
  decorative?: boolean;
};

export function BrandMascot({
  mood = "full",
  size = 160,
  className = "",
  decorative = true,
}: BrandMascotProps) {
  const square = mood === "mark" || mood === "loading";
  const height = square ? size : Math.round(size * 1.05);

  return (
    <Image
      src={MOOD_SRC[mood]}
      alt={decorative ? "" : BRAND.name}
      width={size}
      height={height}
      className={className}
      aria-hidden={decorative || undefined}
      unoptimized
    />
  );
}
