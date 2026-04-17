"use client";

/**
 * Table primitives — light wrappers that apply the shared table tokens.
 *
 * Consumers can either use these directly (`<Table><THead>...`) or compose with
 * native `<table>` tags when they need full control. Tokens referenced:
 * `--table-header`, `--table-row-hover`, `--table-border`, `--border`, `--foreground`,
 * `--muted-foreground`.
 */

import type { HTMLAttributes, TableHTMLAttributes, ThHTMLAttributes, TdHTMLAttributes } from "react";

export function Table({
  className = "",
  children,
  ...rest
}: TableHTMLAttributes<HTMLTableElement>) {
  return (
    <div className="w-full overflow-x-auto">
      <table
        className={`w-full border-collapse text-sm text-[var(--foreground)] ${className}`}
        {...rest}
      >
        {children}
      </table>
    </div>
  );
}

export function THead({
  className = "",
  children,
  ...rest
}: HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead
      className={`bg-[var(--table-header,var(--muted))] border-b border-[var(--table-border,var(--border))] ${className}`}
      {...rest}
    >
      {children}
    </thead>
  );
}

export function TBody({
  className = "",
  children,
  ...rest
}: HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <tbody className={`divide-y divide-[var(--table-border,var(--border))] ${className}`} {...rest}>
      {children}
    </tbody>
  );
}

export function TR({
  className = "",
  children,
  ...rest
}: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={`hover:bg-[var(--table-row-hover,var(--muted))] transition-colors ${className}`}
      {...rest}
    >
      {children}
    </tr>
  );
}

export function TH({
  className = "",
  children,
  ...rest
}: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={`px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)] ${className}`}
      {...rest}
    >
      {children}
    </th>
  );
}

export function TD({
  className = "",
  children,
  ...rest
}: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={`px-3 py-2 ${className}`} {...rest}>
      {children}
    </td>
  );
}
