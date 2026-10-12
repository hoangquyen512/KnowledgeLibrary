import test from "node:test";
import assert from "node:assert/strict";

function normalizePath(href) {
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

function isInternalHref(href, origin = "http://localhost:3000") {
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
      return new URL(href).origin === origin;
    } catch {
      return false;
    }
  }
  return href.startsWith("/");
}

function displayPath(pathname, pendingHref) {
  if (!pendingHref) return pathname;
  return normalizePath(pendingHref);
}

function isActivePath(current, href, options) {
  const c = normalizePath(current);
  const h = normalizePath(href);
  if (options?.exact) return c === h;
  return c === h || c.startsWith(`${h}/`);
}

test("normalizePath strips query, hash, and trailing slash", () => {
  assert.equal(normalizePath("/app/settings/admin?tab=1#top"), "/app/settings/admin");
  assert.equal(normalizePath("/app/settings/"), "/app/settings");
  assert.equal(normalizePath("/"), "/");
});

test("displayPath prefers pending href so tabs can highlight before the route commits", () => {
  assert.equal(displayPath("/app/settings/profile", "/app/settings/admin"), "/app/settings/admin");
  assert.equal(displayPath("/app/settings/profile", null), "/app/settings/profile");
});

test("isActivePath exact vs prefix", () => {
  assert.equal(isActivePath("/app", "/app", { exact: true }), true);
  assert.equal(isActivePath("/app/ask", "/app", { exact: true }), false);
  assert.equal(isActivePath("/app/settings/admin/users", "/app/settings/admin"), true);
  assert.equal(isActivePath("/app/settings/admin", "/app/settings/profile"), false);
});

test("isInternalHref rejects external and special schemes", () => {
  assert.equal(isInternalHref("/app/ask"), true);
  assert.equal(isInternalHref("http://localhost:3000/app"), true);
  assert.equal(isInternalHref("https://example.com/app"), false);
  assert.equal(isInternalHref("mailto:a@b.c"), false);
  assert.equal(isInternalHref("#section"), false);
});
