"use client";

import { useEffect, useRef } from "react";

export interface KeyboardShortcut {
  /** The key to listen for (e.g. "t", "k", "o", "Escape") */
  key: string;
  /** Whether the shortcut requires Cmd (Mac) / Ctrl (Win). Defaults to false. */
  meta?: boolean;
  /** Handler to invoke when the shortcut fires */
  handler: () => void;
  /** Human-readable description for discoverability */
  description: string;
}

const INPUT_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

function isEditableTarget(e: Event): boolean {
  const target = e.target as HTMLElement | null;
  if (!target) return false;
  if (INPUT_TAGS.has(target.tagName)) return true;
  if (target.isContentEditable) return true;
  return false;
}

/**
 * Registers global keyboard shortcuts on `document`.
 *
 * - Automatically handles Mac (`metaKey`) vs Windows/Linux (`ctrlKey`)
 *   for shortcuts that set `meta: true`.
 * - Prevents default browser behaviour for matched shortcuts.
 * - Ignores shortcuts when focus is inside an input, textarea, select,
 *   or contentEditable element (except for Escape, which always fires).
 *
 * Returns the list of registered shortcuts (useful for a help panel).
 */
export function useKeyboardShortcuts(shortcuts: KeyboardShortcut[]): KeyboardShortcut[] {
  // Keep a stable ref so the effect closure always sees the latest handlers
  // without re-registering the listener on every render.
  const shortcutsRef = useRef(shortcuts);
  shortcutsRef.current = shortcuts;

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      for (const shortcut of shortcutsRef.current) {
        const keyMatch = e.key.toLowerCase() === shortcut.key.toLowerCase();
        if (!keyMatch) continue;

        const metaMatch = shortcut.meta
          ? e.metaKey || e.ctrlKey
          : !e.metaKey && !e.ctrlKey;
        if (!metaMatch) continue;

        // Allow Escape everywhere; skip other shortcuts in editable fields
        if (shortcut.key !== "Escape" && isEditableTarget(e)) continue;

        e.preventDefault();
        shortcut.handler();
        return; // first match wins
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  return shortcuts;
}
