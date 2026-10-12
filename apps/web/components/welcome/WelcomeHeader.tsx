import Image from "next/image";
import Link from "next/link";
import { BRAND } from "@/components/brand/tokens";

const NAV_LINKS = [
  { href: "#product", label: "Product" },
  { href: "#security", label: "Security" },
  { href: "#help", label: "Help" },
] as const;

export function WelcomeHeader() {
  return (
    <header className="welcome-nav">
      <Link href="/" className="welcome-nav-brand">
        <Image
          src={BRAND.paths.logoMark}
          alt=""
          width={28}
          height={28}
          className="welcome-nav-mark"
          priority
          unoptimized
        />
        <span>{BRAND.name}</span>
      </Link>

      <nav className="welcome-nav-links" aria-label="Product">
        {NAV_LINKS.map((link) => (
          <a key={link.href} href={link.href} className="welcome-nav-link">
            {link.label}
          </a>
        ))}
      </nav>
    </header>
  );
}
