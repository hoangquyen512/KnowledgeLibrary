"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

const MASKED_URL = "/";

function shouldMaskLocation(): boolean {
  const { pathname, search, hash } = window.location;
  return pathname !== MASKED_URL || Boolean(search) || Boolean(hash);
}

function maskBrowserUrl(): void {
  if (typeof window === "undefined") return;
  if (!shouldMaskLocation()) return;
  // Preserve Next.js history state so client routing keeps working.
  window.history.replaceState(window.history.state, "", MASKED_URL);
}

/**
 * Cosmetic URL mask: Next.js routes stay real; the address bar shows `/` after hydrate.
 * Must not run before React hydration (no blocking inline script) — that made
 * usePathname()/layout router disagree with SSR and caused hydration mismatches.
 */
export function UrlMask() {
  const pathname = usePathname();

  useEffect(() => {
    const originalPushState = History.prototype.pushState;
    const originalReplaceState = History.prototype.replaceState;

    History.prototype.pushState = function pushStateMasked(data, unused, url) {
      const result = originalPushState.apply(this, [data, unused, url]);
      maskBrowserUrl();
      return result;
    };

    History.prototype.replaceState = function replaceStateMasked(data, unused, url) {
      const result = originalReplaceState.apply(this, [data, unused, url]);
      // Avoid recursion: only remask when the visible URL still has a path/query/hash.
      if (shouldMaskLocation()) {
        originalReplaceState.apply(this, [window.history.state, "", MASKED_URL]);
      }
      return result;
    };

    maskBrowserUrl();

    const onPopState = () => {
      queueMicrotask(maskBrowserUrl);
    };
    window.addEventListener("popstate", onPopState);

    // Next.js may rewrite the URL after React effects; keep the bar clean.
    const intervalId = window.setInterval(maskBrowserUrl, 100);

    return () => {
      History.prototype.pushState = originalPushState;
      History.prototype.replaceState = originalReplaceState;
      window.removeEventListener("popstate", onPopState);
      window.clearInterval(intervalId);
    };
  }, []);

  useEffect(() => {
    maskBrowserUrl();
  }, [pathname]);

  return null;
}
