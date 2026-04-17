"use client";

/**
 * ErrorState — error UI with retry CTA.
 *
 * Keeps icon dependency out of the shared package by accepting any ReactNode for `icon`.
 * Consumers typically pass a lucide-react `AlertTriangle` or heroicons equivalent.
 */

import type { ComponentType, ReactNode } from "react";

interface ErrorStateProps {
  /** Accessible message explaining what went wrong. */
  message?: string;
  /** Secondary description under the message. */
  description?: ReactNode;
  /** Optional retry handler — renders the default "Try again" button. */
  onRetry?: () => void;
  /** Custom label for the retry button. */
  retryLabel?: string;
  /** Optional icon override. */
  icon?: ReactNode | ComponentType<{ size?: number; className?: string }>;
  /** Fully custom action node — replaces the retry button if provided. */
  action?: ReactNode;
}

function isIconComponent(
  icon: unknown,
): icon is ComponentType<{ size?: number; className?: string }> {
  return typeof icon === "function";
}

export function ErrorState({
  message = "Something went wrong",
  description,
  onRetry,
  retryLabel = "Try again",
  icon,
  action,
}: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      {icon ? (
        isIconComponent(icon) ? (
          // biome-ignore lint/suspicious/noExplicitAny: component type narrowed by isIconComponent
          <>{(() => { const Icon = icon as any; return <Icon size={40} className="text-[var(--destructive)] mb-3" />; })()}</>
        ) : (
          <div className="text-[var(--destructive)] mb-3">{icon}</div>
        )
      ) : (
        <div
          aria-hidden="true"
          className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-[var(--destructive-muted,rgba(239,68,68,0.15))] text-[var(--destructive)]"
        >
          <span className="text-2xl leading-none font-semibold">!</span>
        </div>
      )}
      <p className="text-sm font-medium text-[var(--foreground)]">{message}</p>
      {description && (
        <p className="text-sm text-[var(--muted-foreground)] mt-1 max-w-md">{description}</p>
      )}
      {action ? (
        <div className="mt-3">{action}</div>
      ) : onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-md border border-[var(--border)] px-4 py-1.5 text-sm text-[var(--foreground)] hover:bg-[var(--muted)]"
        >
          {retryLabel}
        </button>
      ) : null}
    </div>
  );
}
