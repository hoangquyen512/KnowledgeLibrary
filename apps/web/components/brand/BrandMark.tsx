"use client";

import Image from "next/image";
import { BRAND } from "./tokens";

type BrandMarkProps = {
  size?: number;
  className?: string;
  decorative?: boolean;
  title?: string;
  priority?: boolean;
};

/** Mark-only logo; light/dark via CSS to avoid SSR hydration mismatch. */
export function BrandMark({
  size = 28,
  className = "",
  decorative = false,
  title = BRAND.name,
  priority = false,
}: BrandMarkProps) {
  const alt = decorative ? "" : title;
  return (
    <span className={`relative inline-grid place-items-center ${className}`}>
      <Image
        src={BRAND.paths.logoMark}
        alt={alt}
        width={size}
        height={size}
        className="dark:hidden"
        aria-hidden={decorative || undefined}
        style={{ width: size, height: size }}
        priority={priority}
        unoptimized
      />
      <Image
        src={BRAND.paths.logoMarkDark}
        alt={alt}
        width={size}
        height={size}
        className="hidden dark:block"
        aria-hidden={decorative || undefined}
        style={{ width: size, height: size }}
        priority={priority}
        unoptimized
      />
    </span>
  );
}
