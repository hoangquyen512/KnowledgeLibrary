"use client";

import Image from "next/image";
import { BRAND } from "./tokens";

type BrandLogoProps = {
  variant?: "full" | "mark";
  className?: string;
  priority?: boolean;
  showWordmark?: boolean;
};

/**
 * Theme-aware logo without hydration mismatch.
 * Renders both light/dark assets and toggles via CSS (`dark:`), so SSR HTML
 * matches the client (next-themes resolves theme only after mount).
 */
export function BrandLogo({
  variant = "full",
  className = "",
  priority = false,
  showWordmark = true,
}: BrandLogoProps) {
  if (variant === "mark") {
    return (
      <span className={`inline-flex items-center gap-2.5 ${className}`}>
        <span className="relative inline-grid h-8 w-8 place-items-center">
          <Image
            src={BRAND.paths.logoMark}
            alt={showWordmark ? "" : BRAND.name}
            width={32}
            height={32}
            className="h-8 w-8 dark:hidden"
            priority={priority}
            unoptimized
          />
          <Image
            src={BRAND.paths.logoMarkDark}
            alt={showWordmark ? "" : BRAND.name}
            width={32}
            height={32}
            className="hidden h-8 w-8 dark:block"
            priority={priority}
            unoptimized
          />
        </span>
        {showWordmark ? (
          <span className="text-base font-semibold tracking-tight text-foreground sm:text-[17px]">
            {BRAND.name}
          </span>
        ) : null}
      </span>
    );
  }

  return (
    <span className={`relative inline-block w-[min(280px,100%)] ${className}`}>
      <Image
        src={BRAND.paths.logoFullLight}
        alt={BRAND.name}
        width={280}
        height={64}
        className="h-auto w-full dark:hidden"
        priority={priority}
        unoptimized
      />
      <Image
        src={BRAND.paths.logoFullDark}
        alt={BRAND.name}
        width={280}
        height={64}
        className="hidden h-auto w-full dark:block"
        priority={priority}
        unoptimized
      />
    </span>
  );
}
