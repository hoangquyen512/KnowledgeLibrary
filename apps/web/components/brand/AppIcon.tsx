import Image from "next/image";
import { BRAND } from "./tokens";

type AppIconProps = {
  size?: number;
  className?: string;
};

export function AppIcon({ size = 64, className = "" }: AppIconProps) {
  return (
    <Image
      src={BRAND.paths.appIcon}
      alt={BRAND.name}
      width={size}
      height={size}
      className={`rounded-[22%] ${className}`}
      unoptimized
    />
  );
}
