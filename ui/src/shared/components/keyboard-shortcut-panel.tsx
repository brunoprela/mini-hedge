"use client";

import { Modal } from "@mini-hedge/ui";

interface ShortcutEntry {
  description: string;
  keys: string[];
}

const SHORTCUT_GROUPS: { category: string; shortcuts: ShortcutEntry[] }[] = [
  {
    category: "General",
    shortcuts: [
      { description: "Show keyboard shortcuts", keys: ["?"] },
      { description: "Command palette", keys: ["⌘", "K"] },
      { description: "Close panels", keys: ["Esc"] },
    ],
  },
  {
    category: "Trading",
    shortcuts: [
      { description: "Open trade ticket", keys: ["⌘", "T"] },
      { description: "Navigate to orders", keys: ["⌘", "O"] },
    ],
  },
];

interface KeyboardShortcutPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function KeyboardShortcutPanel({ open, onOpenChange }: KeyboardShortcutPanelProps) {
  return (
    <Modal open={open} onClose={() => onOpenChange(false)} maxWidth="sm:max-w-md">
      <div className="space-y-4">
        <h2 className="text-sm font-semibold text-[var(--foreground)]">Keyboard shortcuts</h2>

        {SHORTCUT_GROUPS.map((group) => (
          <div key={group.category} className="space-y-1">
            <h3 className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">
              {group.category}
            </h3>
            <ul className="divide-y divide-[var(--border)]">
              {group.shortcuts.map((shortcut) => (
                <li
                  key={shortcut.description}
                  className="flex items-center justify-between py-2 text-sm"
                >
                  <span className="text-[var(--foreground)]">{shortcut.description}</span>
                  <span className="flex items-center gap-1">
                    {shortcut.keys.map((k, i) => (
                      <kbd
                        key={i}
                        className="inline-flex h-5 min-w-5 items-center justify-center rounded border border-[var(--border)] bg-[var(--muted)] px-1.5 font-mono text-[11px] font-medium text-[var(--muted-foreground)]"
                      >
                        {k}
                      </kbd>
                    ))}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}

        <p className="text-[11px] text-[var(--muted-foreground)] pt-1">
          Press <kbd className="inline-flex h-4 min-w-4 items-center justify-center rounded border border-[var(--border)] bg-[var(--muted)] px-1 font-mono text-[10px] font-medium text-[var(--muted-foreground)]">?</kbd> to dismiss
        </p>
      </div>
    </Modal>
  );
}
