"use client";

/**
 * Right-side slide-out drawer primitive.
 *
 * Bedrock source: tailwind-templates/application-ui-v4/react/overlays/drawers/05-with-sticky-footer.jsx
 *
 * Changes from template:
 * - Palette classes swapped for CSS-variable tokens from src/app/globals.css.
 * - Exposed header title/actions and footer as props so consumers don't re-copy the panel shell.
 * - No structural / layout / transition changes to the panel or its children.
 */

import { Dialog, DialogPanel, DialogTitle } from "@headlessui/react";
import { XMarkIcon } from "@heroicons/react/24/outline";
import type { ReactNode } from "react";

export { Dialog, DialogPanel, DialogTitle };

interface DrawerProps {
  open: boolean;
  onClose: (open: boolean) => void;
  title: ReactNode;
  children: ReactNode;
  /** Optional actions rendered on the right of the header, before the close button. */
  headerActions?: ReactNode;
  /** Optional sticky footer (buttons, status strip, etc.). */
  footer?: ReactNode;
  /** Panel max width. Defaults to `max-w-md` per template. */
  maxWidth?: string;
}

export function Drawer({
  open,
  onClose,
  title,
  children,
  headerActions,
  footer,
  maxWidth = "max-w-md",
}: DrawerProps) {
  return (
    <Dialog open={open} onClose={onClose} className="relative z-50">
      <div className="fixed inset-0 bg-black/40" />

      <div className="fixed inset-0 overflow-hidden">
        <div className="absolute inset-0 overflow-hidden">
          <div className="pointer-events-none fixed inset-y-0 right-0 flex max-w-full pl-10 sm:pl-16">
            <DialogPanel
              transition
              className={`pointer-events-auto w-screen ${maxWidth} transform transition duration-500 ease-in-out data-closed:translate-x-full sm:duration-700`}
            >
              <div className="relative flex h-full flex-col divide-y divide-[var(--border)] bg-[var(--background-raised)] shadow-xl">
                <div className="flex min-h-0 flex-1 flex-col overflow-y-auto py-6">
                  <div className="px-4 sm:px-6">
                    <div className="flex items-start justify-between">
                      <DialogTitle className="text-base font-semibold text-[var(--foreground-bright)]">
                        {title}
                      </DialogTitle>
                      <div className="ml-3 flex h-7 items-center gap-2">
                        {headerActions}
                        <button
                          type="button"
                          onClick={() => onClose(false)}
                          className="relative rounded-md text-[var(--muted-foreground)] hover:text-[var(--foreground)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"
                        >
                          <span className="absolute -inset-2.5" />
                          <span className="sr-only">Close panel</span>
                          <XMarkIcon aria-hidden="true" className="size-6" />
                        </button>
                      </div>
                    </div>
                  </div>
                  <div className="relative mt-6 flex-1 px-4 sm:px-6">{children}</div>
                </div>
                {footer && (
                  <div className="flex shrink-0 justify-end px-4 py-4">{footer}</div>
                )}
              </div>
            </DialogPanel>
          </div>
        </div>
      </div>
    </Dialog>
  );
}
