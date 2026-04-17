"use client";

/**
 * FormField — label + input + error wrapper.
 *
 * Wraps any input-like child with a label, optional hint text, and an inline error.
 * The child receives `aria-invalid` and `aria-describedby` so error-associated
 * messaging is picked up by screen readers.
 */

import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from "react";

interface FormFieldProps {
  label: ReactNode;
  /** Optional helper text shown under the input. */
  hint?: ReactNode;
  /** Error message — when present swaps hint out and marks the field invalid. */
  error?: ReactNode;
  /** Whether the field is required — appends an asterisk to the label. */
  required?: boolean;
  /** The input child. Must be a single React element. */
  children: ReactElement;
  className?: string;
}

export function FormField({
  label,
  hint,
  error,
  required = false,
  children,
  className = "",
}: FormFieldProps) {
  const autoId = useId();
  const childProps = (children as ReactElement<{ id?: string }>).props ?? {};
  const id = childProps.id ?? autoId;
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;

  const describedBy = [error ? errorId : null, !error && hint ? hintId : null]
    .filter(Boolean)
    .join(" ") || undefined;

  const enhanced = isValidElement(children)
    ? cloneElement(children, {
        id,
        "aria-invalid": error ? true : undefined,
        "aria-describedby": describedBy,
      } as Record<string, unknown>)
    : children;

  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <label htmlFor={id} className="text-xs font-medium text-[var(--foreground)]">
        {label}
        {required && <span className="ml-0.5 text-[var(--destructive)]">*</span>}
      </label>
      {enhanced}
      {error ? (
        <p id={errorId} className="text-xs text-[var(--destructive)]">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="text-xs text-[var(--muted-foreground)]">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
