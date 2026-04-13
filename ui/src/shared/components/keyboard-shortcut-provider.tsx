"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useCallback, useMemo, useState } from "react";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import type { KeyboardShortcut } from "@/shared/hooks/use-keyboard-shortcuts";
import { useKeyboardShortcuts } from "@/shared/hooks/use-keyboard-shortcuts";
import { useTradeTicket } from "@/shared/components/trade-ticket-provider";
import { KeyboardShortcutPanel } from "@/shared/components/keyboard-shortcut-panel";

/**
 * Registers the app-wide keyboard shortcuts.
 *
 * Must be rendered inside `<TradeTicketProvider>` so it can access the
 * trade ticket context.
 */
export function KeyboardShortcutProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { fundSlug } = useFundContext();
  const { isOpen, openTradeTicket, closeTradeTicket } = useTradeTicket();
  const [shortcutPanelOpen, setShortcutPanelOpen] = useState(false);

  const toggleShortcutPanel = useCallback(() => {
    setShortcutPanelOpen((prev) => !prev);
  }, []);

  const shortcuts = useMemo<KeyboardShortcut[]>(
    () => [
      {
        key: "t",
        meta: true,
        description: "Open trade ticket",
        handler: () => openTradeTicket(),
      },
      {
        key: "o",
        meta: true,
        description: "Navigate to orders",
        handler: () => router.push(`/${fundSlug}/orders`),
      },
      {
        key: "Escape",
        description: "Close trade ticket",
        handler: () => {
          if (isOpen) closeTradeTicket();
        },
      },
      {
        key: "?",
        description: "Show keyboard shortcuts",
        handler: toggleShortcutPanel,
      },
      // Cmd+K is handled by useCommandPalette() in the top-bar already.
      // Listed here for discoverability only — no handler needed.
    ],
    [closeTradeTicket, fundSlug, isOpen, openTradeTicket, router, toggleShortcutPanel],
  );

  useKeyboardShortcuts(shortcuts);

  return (
    <>
      {children}
      <KeyboardShortcutPanel open={shortcutPanelOpen} onOpenChange={setShortcutPanelOpen} />
    </>
  );
}
