"use client";

/**
 * Command palette primitive.
 *
 * Bedrock source: tailwind-templates/application-ui-v4/react/navigation/command-palettes/08-with-groups.jsx
 *
 * Changes from template:
 * - Palette classes swapped for CSS-variable tokens from src/app/globals.css.
 * - Accepts grouped items via props instead of hardcoded data (consumer supplies filtering).
 * - No structural / layout / transition changes.
 */

import {
  Combobox,
  ComboboxInput,
  ComboboxOption,
  ComboboxOptions,
  Dialog,
  DialogBackdrop,
  DialogPanel,
} from "@headlessui/react";
import { MagnifyingGlassIcon } from "@heroicons/react/20/solid";
import type { ReactNode } from "react";

export interface CommandPaletteItem {
  id: string;
  label: string;
  icon?: ReactNode;
  onSelect: () => void;
}

export interface CommandPaletteGroup {
  category: string;
  items: CommandPaletteItem[];
}

interface CommandPaletteProps {
  open: boolean;
  onClose: (open: boolean) => void;
  query: string;
  onQueryChange: (query: string) => void;
  groups: CommandPaletteGroup[];
  emptyState?: ReactNode;
  placeholder?: string;
}

export function CommandPalette({
  open,
  onClose,
  query,
  onQueryChange,
  groups,
  emptyState,
  placeholder = "Search...",
}: CommandPaletteProps) {
  const isEmpty = groups.every((g) => g.items.length === 0);

  return (
    <Dialog
      transition
      className="relative z-50"
      open={open}
      onClose={() => {
        onClose(false);
        onQueryChange("");
      }}
    >
      <DialogBackdrop
        transition
        className="fixed inset-0 bg-black/50 transition-opacity data-closed:opacity-0 data-enter:duration-300 data-enter:ease-out data-leave:duration-200 data-leave:ease-in"
      />

      <div className="fixed inset-0 z-10 w-screen overflow-y-auto p-4 sm:p-6 md:p-20">
        <DialogPanel
          transition
          className="mx-auto max-w-xl transform overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-2xl transition-all data-closed:scale-95 data-closed:opacity-0 data-enter:duration-300 data-enter:ease-out data-leave:duration-200 data-leave:ease-in"
        >
          <Combobox<CommandPaletteItem>
            onChange={(item) => {
              if (item) {
                item.onSelect();
              }
            }}
          >
            <div className="grid grid-cols-1">
              <ComboboxInput
                autoFocus
                className="col-start-1 row-start-1 h-12 w-full bg-transparent pr-4 pl-11 text-sm text-[var(--foreground)] outline-hidden placeholder:text-[var(--muted-foreground)]"
                placeholder={placeholder}
                value={query}
                onChange={(event) => onQueryChange(event.target.value)}
              />
              <MagnifyingGlassIcon
                className="pointer-events-none col-start-1 row-start-1 ml-4 size-5 self-center text-[var(--muted-foreground)]"
                aria-hidden="true"
              />
            </div>

            {!isEmpty && (
              <ComboboxOptions
                static
                as="ul"
                className="max-h-80 scroll-pt-11 scroll-pb-2 space-y-2 overflow-y-auto border-t border-[var(--border)] pb-2"
              >
                {groups
                  .filter((g) => g.items.length > 0)
                  .map((group) => (
                    <li key={group.category}>
                      <h2 className="bg-[var(--muted)] px-4 py-2.5 text-xs font-semibold text-[var(--foreground-bright)]">
                        {group.category}
                      </h2>
                      <ul className="mt-2 text-sm text-[var(--foreground)]">
                        {group.items.map((item) => (
                          <ComboboxOption
                            key={item.id}
                            value={item}
                            className="flex cursor-default items-center gap-3 px-4 py-2 select-none data-focus:bg-[var(--primary)] data-focus:text-[var(--primary-foreground)] data-focus:outline-hidden"
                          >
                            {item.icon && (
                              <span className="shrink-0 text-[var(--muted-foreground)] group-data-focus:text-[var(--primary-foreground)]">
                                {item.icon}
                              </span>
                            )}
                            <span>{item.label}</span>
                          </ComboboxOption>
                        ))}
                      </ul>
                    </li>
                  ))}
              </ComboboxOptions>
            )}

            {isEmpty && (
              <div className="border-t border-[var(--border)] px-6 py-14 text-center text-sm sm:px-14">
                {emptyState ?? (
                  <p className="text-[var(--muted-foreground)]">
                    {query === "" ? "Start typing to search..." : "No results found."}
                  </p>
                )}
              </div>
            )}
          </Combobox>
        </DialogPanel>
      </div>
    </Dialog>
  );
}
