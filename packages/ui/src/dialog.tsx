"use client";

/**
 * Modal dialog primitive.
 *
 * Bedrock source: tailwind-templates/application-ui-v4/react/overlays/modal-dialogs/01-centered-with-single-action.jsx
 *
 * Changes from template:
 * - Palette classes swapped for CSS-variable tokens from src/app/globals.css.
 * - No structural / layout / transition changes.
 */

import {
  Dialog,
  DialogBackdrop,
  DialogPanel,
  DialogTitle,
} from "@headlessui/react";
import type { ReactNode } from "react";

export { Dialog, DialogBackdrop, DialogPanel, DialogTitle };

interface ModalProps {
  open: boolean;
  onClose: (open: boolean) => void;
  children: ReactNode;
  /** Max width of the panel. Defaults to `sm:max-w-lg`. */
  maxWidth?: string;
}

/**
 * Centered modal panel with backdrop and transition.
 * Matches the skeleton of modal-dialogs/01-centered-with-single-action.jsx.
 */
export function Modal({ open, onClose, children, maxWidth = "sm:max-w-lg" }: ModalProps) {
  return (
    <Dialog open={open} onClose={onClose} className="relative z-50">
      <DialogBackdrop
        transition
        className="fixed inset-0 bg-black/50 transition-opacity data-closed:opacity-0 data-enter:duration-300 data-enter:ease-out data-leave:duration-200 data-leave:ease-in"
      />

      <div className="fixed inset-0 z-10 w-screen overflow-y-auto">
        <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
          <DialogPanel
            transition
            className={`relative transform overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 pt-5 pb-4 text-left shadow-xl transition-all data-closed:translate-y-4 data-closed:opacity-0 data-enter:duration-300 data-enter:ease-out data-leave:duration-200 data-leave:ease-in sm:my-8 sm:w-full sm:p-6 data-closed:sm:translate-y-0 data-closed:sm:scale-95 ${maxWidth}`}
          >
            {children}
          </DialogPanel>
        </div>
      </div>
    </Dialog>
  );
}
