"use client";

/**
 * Card — bordered container matching the bedrock card shell.
 * Composable header/body/footer via {@link CardHeader}/{@link CardBody}/{@link CardFooter}.
 */

import { forwardRef, type HTMLAttributes, type ReactNode } from "react";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  /** Remove the default padding. */
  noPadding?: boolean;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(function Card(
  { children, noPadding = false, className = "", ...rest },
  ref,
) {
  const classes = [
    "rounded-lg border border-[var(--border)] bg-[var(--card)] text-[var(--card-foreground,var(--foreground))]",
    noPadding ? "" : "p-4",
    className,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <div ref={ref} className={classes} {...rest}>
      {children}
    </div>
  );
});

export function CardHeader({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`flex items-center justify-between border-b border-[var(--border)] px-4 py-3 ${className}`}
    >
      {children}
    </div>
  );
}

export function CardBody({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`p-4 ${className}`}>{children}</div>;
}

export function CardFooter({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`border-t border-[var(--border)] px-4 py-3 flex items-center justify-end gap-2 ${className}`}
    >
      {children}
    </div>
  );
}
