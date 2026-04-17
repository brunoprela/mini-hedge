"use client";

/**
 * Toast — thin wrapper around `sonner` so consumers can import toast helpers
 * from the shared package and change the underlying library in one place.
 *
 * The `sonner` dependency is declared at the consumer level (each UI package
 * already ships it) — we do not add a hard dependency here to keep the shared
 * package zero-install.
 */

export {
  toast,
  Toaster,
  type ToasterProps,
  type ToastT,
} from "sonner";
