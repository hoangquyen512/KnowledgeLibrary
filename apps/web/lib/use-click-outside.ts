"use client";

import { useEffect, useRef, type RefObject } from "react";

/**
 * Close popovers/menus when clicking outside the root element, or pressing Escape.
 */
export function useClickOutside(
  ref: RefObject<HTMLElement | null>,
  active: boolean,
  onClose: () => void,
) {
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!active) return;

    const onPointer = (event: MouseEvent | TouchEvent) => {
      const root = ref.current;
      const target = event.target as Node | null;
      if (!root || !target || root.contains(target)) return;
      onCloseRef.current();
    };

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCloseRef.current();
    };

    document.addEventListener("mousedown", onPointer);
    document.addEventListener("touchstart", onPointer, { passive: true });
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("touchstart", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [active, ref]);
}
