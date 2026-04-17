"use client";

/**
 * EmptyState — no-data UI with optional CTA.
 *
 * Generic `icon` slot accepts any ReactNode (typically a lucide-react or heroicons icon).
 * Keep it agnostic — the shared package should not hard-depend on a specific icon set.
 */

import type { ComponentType, ReactNode } from "react";

interface EmptyStateProps {
  /**
   * Optional icon — accepts either a ReactNode (already-rendered) or an icon component.
   * Icon components are rendered with `size={40}`.
   */
  icon?: ReactNode | ComponentType<{ size?: number; className?: string }>;
  title: string;
  description?: ReactNode;
  /** Optional call-to-action rendered below the description. */
  action?: ReactNode;
}

function isIconComponent(
  icon: unknown,
): icon is ComponentType<{ size?: number; className?: string }> {
  return typeof icon === "function";
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      {icon &&
        (isIconComponent(icon) ? (
          // biome-ignore lint/suspicious/noExplicitAny: component type narrowed by isIconComponent
          <>{(() => { const Icon = icon as any; return <Icon size={40} className="text-[var(--muted-foreground)] mb-3" />; })()}</>
        ) : (
          <div className="text-[var(--muted-foreground)] mb-3">{icon}</div>
        ))}
      <p className="text-sm font-medium text-[var(--foreground)]">{title}</p>
      {description && (
        <p className="text-sm text-[var(--muted-foreground)] mt-1 max-w-md">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
