"use client";

/**
 * LoadingSkeleton — shimmer placeholders.
 *
 * Variants:
 *   - `rectangle` (default): a single animated rectangle sized by width/height.
 *   - `text`: stacked text lines.
 *   - `card`: a grid of card placeholders.
 *   - `table-row`: table-shaped rows + header.
 */

type Variant = "rectangle" | "text" | "card" | "table-row";

interface LoadingSkeletonProps {
  variant?: Variant;
  /** Rows count for `text` / `table-row` variants. */
  rows?: number;
  /** Columns count for `table-row` variant. */
  columns?: number;
  /** Card count for `card` variant. */
  count?: number;
  /** Width for rectangle variant — Tailwind class or CSS value. */
  width?: string;
  /** Height for rectangle variant — Tailwind class or CSS value. */
  height?: string;
  className?: string;
}

export function LoadingSkeleton({
  variant = "rectangle",
  rows = 5,
  columns = 4,
  count = 3,
  width,
  height,
  className = "",
}: LoadingSkeletonProps) {
  if (variant === "text") {
    return (
      <div className={`space-y-2 ${className}`}>
        {Array.from({ length: rows }).map((_, r) => (
          <div
            // biome-ignore lint/suspicious/noArrayIndexKey: text skeleton rows are identical placeholders
            key={`line-${r}`}
            className="h-3 rounded bg-[var(--muted)] animate-pulse"
            style={{ width: r === rows - 1 ? "70%" : "100%" }}
          />
        ))}
      </div>
    );
  }

  if (variant === "card") {
    return (
      <div className={`grid grid-cols-1 sm:grid-cols-3 gap-4 ${className}`}>
        {Array.from({ length: count }).map((_, i) => (
          <div
            // biome-ignore lint/suspicious/noArrayIndexKey: card skeletons are identical placeholders
            key={`card-${i}`}
            className="rounded-lg border border-[var(--border)] p-6 bg-[var(--card)] animate-pulse"
          >
            <div className="flex items-center gap-3 mb-3">
              <div className="w-5 h-5 rounded bg-[var(--muted)]" />
              <div className="h-4 w-20 rounded bg-[var(--muted)]" />
            </div>
            <div className="h-8 w-16 rounded bg-[var(--muted)]" />
          </div>
        ))}
      </div>
    );
  }

  if (variant === "table-row") {
    return (
      <div className={`w-full ${className}`}>
        <div className="flex gap-4 mb-3">
          {Array.from({ length: columns }).map((_, c) => (
            <div
              // biome-ignore lint/suspicious/noArrayIndexKey: header cells are identical placeholders
              key={`th-${c}`}
              className="h-4 rounded bg-[var(--muted)] animate-pulse"
              style={{ flex: c === 0 ? 2 : 1 }}
            />
          ))}
        </div>
        {Array.from({ length: rows }).map((_, r) => (
          <div
            // biome-ignore lint/suspicious/noArrayIndexKey: skeleton rows are identical placeholders
            key={`row-${r}`}
            className="flex gap-4 py-3 border-b border-[var(--border)]"
          >
            {Array.from({ length: columns }).map((_, c) => (
              <div
                // biome-ignore lint/suspicious/noArrayIndexKey: skeleton cells are identical placeholders
                key={`cell-${r}-${c}`}
                className="h-4 rounded bg-[var(--muted)] animate-pulse"
                style={{ flex: c === 0 ? 2 : 1, opacity: 0.6 }}
              />
            ))}
          </div>
        ))}
      </div>
    );
  }

  // rectangle
  return (
    <div
      className={`rounded bg-[var(--muted)] animate-pulse ${className}`}
      style={{ width: width ?? "100%", height: height ?? "1rem" }}
    />
  );
}

/** Convenience wrapper — table-row skeleton preset. */
export function TableSkeleton({ rows = 5, columns = 4 }: { rows?: number; columns?: number }) {
  return <LoadingSkeleton variant="table-row" rows={rows} columns={columns} />;
}

/** Convenience wrapper — card skeleton preset. */
export function CardSkeleton({ count = 3 }: { count?: number }) {
  return <LoadingSkeleton variant="card" count={count} />;
}
