import type { Metadata, Viewport } from "next";
import { Source_Serif_4, DM_Sans } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";

const display = Source_Serif_4({
  subsets: ["latin", "latin-ext"],
  variable: "--font-source-serif",
});

const sans = DM_Sans({
  subsets: ["latin", "latin-ext"],
  variable: "--font-geist-sans",
});

export const metadata: Metadata = {
  title: {
    default: "Knowledge Library",
    template: "%s · Knowledge Library",
  },
  description: "Explore • Understand • Grow — organize and analyze knowledge with grounded AI.",
  applicationName: "Knowledge Library",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: [
      { url: "/brand/favicon/favicon-16x16.png", sizes: "16x16", type: "image/png" },
      { url: "/brand/favicon/favicon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/brand/app-icons/icon-192.png", sizes: "192x192", type: "image/png" },
    ],
    apple: [{ url: "/brand/app-icons/icon-180.png", sizes: "180x180", type: "image/png" }],
    shortcut: ["/brand/favicon/favicon.ico"],
  },
  openGraph: {
    title: "Knowledge Library",
    description: "Explore • Understand • Grow",
    siteName: "Knowledge Library",
    images: [{ url: "/brand/social/og-image.png", width: 1200, height: 630, alt: "Knowledge Library" }],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Knowledge Library",
    description: "Explore • Understand • Grow",
    images: ["/brand/social/og-image.png"],
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#102A6A" },
    { media: "(prefers-color-scheme: dark)", color: "#102A6A" },
  ],
  colorScheme: "light dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${sans.variable} ${display.variable} font-sans antialiased`}>
        {/* URL masking runs after hydration in UrlMask — do not replaceState here or
            usePathname()/layout router can hydrate as `/` and mismatch SSR. */}
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
