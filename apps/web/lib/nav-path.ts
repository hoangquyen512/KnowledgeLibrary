/** Normalize an href or pathname for navigation matching (no trailing slash, no query/hash). */
export function normalizePath(href: string): string {
  if (!href) return "/";
  const trimmed = href.trim();
  if (
    trimmed.startsWith("#") ||
    trimmed.startsWith("javascript:") ||
    trimmed.startsWith("mailto:") ||
    trimmed.startsWith("tel:")
  ) {
    return trimmed;
  }
  try {
    const url =
      trimmed.startsWith("http://") || trimmed.startsWith("https://")
        ? new URL(trimmed)
        : new URL(trimmed, "http://nav.local");
    let path = url.pathname || "/";
    if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);
    return path || "/";
  } catch {
    const path = trimmed.split("?")[0].split("#")[0] || "/";
    if (path.length > 1 && path.endsWith("/")) return path.slice(0, -1);
    return path || "/";
  }
}

export function isInternalHref(href: string): boolean {
  if (
    !href ||
    href.startsWith("#") ||
    href.startsWith("mailto:") ||
    href.startsWith("tel:") ||
    href.startsWith("javascript:")
  ) {
    return false;
  }
  if (href.startsWith("http://") || href.startsWith("https://")) {
    try {
      if (typeof window === "undefined") return false;
      return new URL(href).origin === window.location.origin;
    } catch {
      return false;
    }
  }
  return href.startsWith("/");
}

export function displayPath(pathname: string, pendingHref: string | null): string {
  if (!pendingHref) return pathname;
  return normalizePath(pendingHref);
}

export function isActivePath(
  current: string,
  href: string,
  options?: { exact?: boolean },
): boolean {
  const c = normalizePath(current);
  const h = normalizePath(href);
  if (options?.exact) return c === h;
  return c === h || c.startsWith(`${h}/`);
}
