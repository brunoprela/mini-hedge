"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Returns a CSS class name that flashes green or red when a numeric value
 * changes between renders. The flash clears after ~700 ms.
 */
export function useFlashOnChange(value: number): string {
  const prevRef = useRef<number>(value);
  const [flash, setFlash] = useState<"flash-up" | "flash-down" | "">("");

  useEffect(() => {
    const prev = prevRef.current;
    prevRef.current = value;

    if (prev === value || prev === 0) return;

    if (value > prev) {
      setFlash("flash-up");
    } else {
      setFlash("flash-down");
    }

    const timer = setTimeout(() => setFlash(""), 700);
    return () => clearTimeout(timer);
  }, [value]);

  return flash;
}
