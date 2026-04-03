export function TableSkeleton({ rows = 5, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <div className="w-full">
      <div className="flex gap-4 mb-3">
        {Array.from({ length: columns }).map((_, c) => (
          <div
            key={`th-${c}`}
            className="h-4 rounded bg-[var(--muted)] animate-pulse"
            style={{ flex: c === 0 ? 2 : 1 }}
          />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={`row-${r}`} className="flex gap-4 py-3 border-b border-[var(--border)]">
          {Array.from({ length: columns }).map((_, c) => (
            <div
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

export function CardSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={`card-${i}`}
          className="rounded-lg border border-[var(--border)] p-6 bg-white animate-pulse"
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
