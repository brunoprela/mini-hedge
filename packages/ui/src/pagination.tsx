"use client";

/**
 * Pagination — prev/next buttons with page info and numbered jumps.
 *
 * API is backwards-compatible with both of the duplicated variants:
 *   - ops-ui `{ total, limit, page, onPageChange }` signature (prev/next only).
 *   - ui `{ page, totalPages, totalItems, pageSize, onPageChange }` with numbered pages.
 *
 * Provide either `{ total, limit }` or `{ totalItems, pageSize, totalPages }`.
 * Set `showNumbers={false}` to force the compact prev/next-only layout.
 */

interface PaginationProps {
  page: number;
  onPageChange: (page: number) => void;
  /** Total number of items. Alias: `totalItems`. */
  total?: number;
  totalItems?: number;
  /** Items per page. Alias: `pageSize`. */
  limit?: number;
  pageSize?: number;
  /** Optional explicit total page count. If omitted, derived from total / limit. */
  totalPages?: number;
  /** Show numbered page buttons with ellipses. Defaults to true. */
  showNumbers?: boolean;
  /** Previous button label. */
  prevLabel?: string;
  /** Next button label. */
  nextLabel?: string;
}

export function Pagination({
  page,
  onPageChange,
  total,
  totalItems,
  limit,
  pageSize,
  totalPages: totalPagesProp,
  showNumbers = true,
  prevLabel = "Previous",
  nextLabel = "Next",
}: PaginationProps) {
  const resolvedTotal = totalItems ?? total ?? 0;
  const resolvedPageSize = pageSize ?? limit ?? 10;
  const resolvedTotalPages =
    totalPagesProp ?? Math.max(1, Math.ceil(resolvedTotal / resolvedPageSize));

  if (resolvedTotalPages <= 1) return null;

  const start = page * resolvedPageSize + 1;
  const end = Math.min((page + 1) * resolvedPageSize, resolvedTotal);

  // Build visible page numbers: always show first, last, and pages around current
  const pages: (number | "ellipsis")[] = [];
  for (let i = 0; i < resolvedTotalPages; i++) {
    if (i === 0 || i === resolvedTotalPages - 1 || (i >= page - 1 && i <= page + 1)) {
      pages.push(i);
    } else if (pages[pages.length - 1] !== "ellipsis") {
      pages.push("ellipsis");
    }
  }

  return (
    <div className="flex items-center justify-between text-sm text-[var(--muted-foreground)]">
      <span>
        {resolvedTotal > 0
          ? `Showing ${start}\u2013${end} of ${resolvedTotal} results`
          : `Page ${page + 1} of ${resolvedTotalPages}`}
      </span>

      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => onPageChange(Math.max(0, page - 1))}
          disabled={page === 0}
          className="inline-flex h-8 items-center rounded-md border border-[var(--border)] bg-[var(--background,transparent)] px-3 text-[var(--foreground)] disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[var(--accent,var(--muted))] transition-colors"
        >
          {prevLabel}
        </button>

        {showNumbers &&
          pages.map((p, idx) =>
            p === "ellipsis" ? (
              <span
                // biome-ignore lint/suspicious/noArrayIndexKey: ellipsis items have no stable key
                key={`ellipsis-${idx}`}
                className="px-1"
              >
                ...
              </span>
            ) : (
              <button
                type="button"
                key={p}
                onClick={() => onPageChange(p)}
                className={`inline-flex h-8 w-8 items-center justify-center rounded-md text-sm transition-colors ${
                  p === page
                    ? "bg-[var(--primary)] text-[var(--primary-foreground)] font-medium"
                    : "border border-[var(--border)] bg-[var(--background,transparent)] text-[var(--foreground)] hover:bg-[var(--accent,var(--muted))]"
                }`}
              >
                {p + 1}
              </button>
            ),
          )}

        <button
          type="button"
          onClick={() => onPageChange(Math.min(resolvedTotalPages - 1, page + 1))}
          disabled={page >= resolvedTotalPages - 1}
          className="inline-flex h-8 items-center rounded-md border border-[var(--border)] bg-[var(--background,transparent)] px-3 text-[var(--foreground)] disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[var(--accent,var(--muted))] transition-colors"
        >
          {nextLabel}
        </button>
      </div>
    </div>
  );
}
