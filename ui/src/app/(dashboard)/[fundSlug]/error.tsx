"use client";

import { useEffect } from "react";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Dashboard error:", error);
  }, [error]);

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8">
      <div className="rounded-lg border border-[var(--destructive)] bg-[var(--destructive-muted)] p-6 text-center">
        <h2 className="mb-2 text-lg font-semibold text-[var(--destructive)]">
          Something went wrong
        </h2>
        <p className="mb-4 text-sm text-[var(--destructive)]">
          {error.message || "An unexpected error occurred."}
        </p>
        <button
          type="button"
          onClick={reset}
          className="rounded-md bg-[var(--destructive)] px-4 py-2 text-sm font-medium text-white hover:opacity-80"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
