"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { displayPath as resolveDisplayPath, isInternalHref, normalizePath } from "@/lib/nav-path";

type NavContextValue = {
  pendingHref: string | null;
  start: (href: string) => void;
  complete: () => void;
};

const NavContext = createContext<NavContextValue | null>(null);

export function useNavigationProgress() {
  return useContext(NavContext);
}

export function useDisplayPath() {
  const pathname = usePathname();
  const nav = useNavigationProgress();
  return resolveDisplayPath(pathname, nav?.pendingHref ?? null);
}

type AppNavigateOptions = { scroll?: boolean; feedback?: boolean };

function nextNavOptions(options?: AppNavigateOptions) {
  if (!options) return undefined;
  const { feedback: _feedback, ...rest } = options;
  return Object.keys(rest).length ? rest : undefined;
}

export function useAppRouter() {
  const router = useRouter();
  const nav = useNavigationProgress();
  return useMemo(
    () => ({
      push(href: string, options?: AppNavigateOptions) {
        if (options?.feedback !== false) nav?.start(href);
        return router.push(href, nextNavOptions(options));
      },
      replace(href: string, options?: AppNavigateOptions) {
        if (options?.feedback) nav?.start(href);
        return router.replace(href, nextNavOptions(options));
      },
      back: () => router.back(),
      forward: () => router.forward(),
      refresh: () => router.refresh(),
      prefetch: (href: string) => router.prefetch(href),
    }),
    [nav, router],
  );
}

function linkHrefFromEvent(event: MouseEvent): string | null {
  if (event.defaultPrevented || event.button !== 0) return null;
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return null;
  const target = event.target;
  if (!(target instanceof Element)) return null;
  const anchor = target.closest("a");
  if (!anchor) return null;
  if (anchor.target && anchor.target !== "_self") return null;
  if (anchor.hasAttribute("download") || anchor.getAttribute("data-nav-silent") != null) return null;
  const href = anchor.getAttribute("href");
  if (!href || !isInternalHref(href)) return null;
  return href;
}

export function NavigationProgressProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [pendingHref, setPendingHref] = useState<string | null>(null);
  const [bar, setBar] = useState({ visible: false, width: 0 });
  const originPathRef = useRef<string | null>(null);
  const genRef = useRef(0);

  const complete = useCallback(() => {
    const gen = genRef.current;
    setBar({ visible: true, width: 100 });
    window.setTimeout(() => {
      if (genRef.current !== gen) return;
      setPendingHref(null);
      originPathRef.current = null;
      setBar({ visible: false, width: 0 });
    }, 180);
  }, []);

  const start = useCallback(
    (href: string) => {
      const next = normalizePath(href);
      // Prefer Next.js pathname — window.location may be masked to `/`.
      const current = normalizePath(pathname);
      if (next === current) return;
      genRef.current += 1;
      originPathRef.current = current;
      setPendingHref(next);
      setBar({ visible: true, width: 16 });
    },
    [pathname],
  );

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      const href = linkHrefFromEvent(event);
      if (href) start(href);
    };
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, [start]);

  useEffect(() => {
    if (!pendingHref) return;
    const now = normalizePath(pathname);
    if (now === pendingHref) {
      complete();
      return;
    }
    if (originPathRef.current && now !== originPathRef.current) {
      complete();
    }
  }, [pathname, pendingHref, complete]);

  useEffect(() => {
    if (!pendingHref) return;
    const timer = window.setInterval(() => {
      setBar((prev) => {
        if (!prev.visible || prev.width >= 86) return prev;
        return { ...prev, width: Math.min(86, prev.width + Math.max(1.2, (86 - prev.width) * 0.12)) };
      });
    }, 180);
    return () => window.clearInterval(timer);
  }, [pendingHref]);

  useEffect(() => {
    if (!pendingHref) return;
    const timeout = window.setTimeout(() => complete(), 12_000);
    return () => window.clearTimeout(timeout);
  }, [pendingHref, complete]);

  useEffect(() => {
    document.body.dataset.navPending = pendingHref ? "true" : "false";
    return () => {
      delete document.body.dataset.navPending;
    };
  }, [pendingHref]);

  const value = useMemo(
    () => ({ pendingHref, start, complete }),
    [pendingHref, start, complete],
  );

  return (
    <NavContext.Provider value={value}>
      <div
        className="nav-progress"
        role="progressbar"
        aria-hidden={!bar.visible}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={bar.visible ? Math.round(bar.width) : 0}
        data-visible={bar.visible ? "true" : "false"}
        style={{ width: `${bar.width}%` }}
      />
      {children}
    </NavContext.Provider>
  );
}
