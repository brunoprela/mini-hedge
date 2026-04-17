"use client";

import {
  EmptyState,
  ErrorState,
  Pagination,
  TableSkeleton,
} from "@mini-hedge/ui";
import type { LucideIcon } from "lucide-react";
import { Pencil, Plus } from "lucide-react";
import type { ReactNode } from "react";

/**
 * ResourcePage — minimal shell for admin CRUD list pages.
 *
 * Renders the page header, an optional create card (rendered by caller),
 * loading / empty / error states, the data table, and pagination.
 *
 * The caller owns:
 *   - zod schemas + RHF form state for create and edit
 *   - the create <form> JSX (passed as `createForm`)
 *   - the edit modal JSX + edit-form state
 *   - fetching (react-query) and mutations (including optimistic updates)
 *
 * This is deliberately a thin abstraction — see `customers/page.tsx` and
 * `users/page.tsx` for callers.
 */
export interface ResourceColumn<TRow> {
  key: string;
  header: string;
  render: (row: TRow) => ReactNode;
}

export interface ResourcePageProps<TRow> {
  title: string;
  /** Label used on the create button ("Create Customer"). */
  createLabel?: string;
  /** Icon shown in the empty state. */
  emptyIcon: LucideIcon;
  emptyTitle: string;
  emptyDescription: string;

  rows: TRow[] | undefined;
  total: number | undefined;
  limit: number;
  page: number;
  onPageChange: (page: number) => void;

  isLoading: boolean;
  isError: boolean;
  errorMessage?: string;
  onRetry: () => void;

  columns: ResourceColumn<TRow>[];
  rowKey: (row: TRow) => string;

  canCreate: boolean;
  canEdit: boolean;

  /** Whether the create card is visible. */
  showCreate: boolean;
  onOpenCreate: () => void;
  /**
   * Create form JSX. Caller owns the RHF form, zod schema, and submit wiring;
   * ResourcePage only renders the container card around it when
   * `showCreate` is true.
   */
  createForm?: ReactNode;

  onEdit?: (row: TRow) => void;
  /**
   * Edit modal JSX. Rendered after the table so the caller can manage its
   * own state (RHF form, open flag).
   */
  editModal?: ReactNode;
}

export function ResourcePage<TRow>({
  title,
  createLabel,
  emptyIcon,
  emptyTitle,
  emptyDescription,
  rows,
  total,
  limit,
  page,
  onPageChange,
  isLoading,
  isError,
  errorMessage,
  onRetry,
  columns,
  rowKey,
  canCreate,
  canEdit,
  showCreate,
  onOpenCreate,
  createForm,
  onEdit,
  editModal,
}: ResourcePageProps<TRow>) {
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">{title}</h2>
        {canCreate && createLabel && (
          <button
            type="button"
            onClick={onOpenCreate}
            className="flex items-center gap-1 rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm text-white hover:opacity-90"
          >
            <Plus size={14} /> {createLabel}
          </button>
        )}
      </div>

      {canCreate && showCreate && createForm}

      {isLoading ? (
        <TableSkeleton rows={5} columns={columns.length + (canEdit ? 1 : 0)} />
      ) : isError ? (
        <ErrorState message={errorMessage ?? "Something went wrong"} onRetry={onRetry} />
      ) : rows && rows.length === 0 ? (
        <EmptyState
          icon={emptyIcon}
          title={emptyTitle}
          description={emptyDescription}
        />
      ) : (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                {columns.map((col) => (
                  <th key={col.key} className="py-2 font-medium">
                    {col.header}
                  </th>
                ))}
                {canEdit && <th className="py-2 font-medium">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {rows?.map((row) => (
                <tr key={rowKey(row)} className="border-b border-[var(--border)]">
                  {columns.map((col) => (
                    <td key={col.key} className="py-2">
                      {col.render(row)}
                    </td>
                  ))}
                  {canEdit && (
                    <td className="py-2">
                      {onEdit && (
                        <button
                          type="button"
                          onClick={() => onEdit(row)}
                          className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                          title="Edit"
                        >
                          <Pencil size={14} />
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          {typeof total === "number" && (
            <Pagination
              total={total}
              limit={limit}
              page={page}
              onPageChange={onPageChange}
            />
          )}
        </>
      )}

      {editModal}
    </div>
  );
}
