"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";

export function PayloadCell({ payload }: { payload: Record<string, unknown> }) {
  const [expanded, setExpanded] = useState(false);
  const keys = Object.keys(payload);
  if (keys.length === 0) return <span className="text-[var(--muted-foreground)]">-</span>;

  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
      >
        {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        {keys.length} {keys.length === 1 ? "field" : "fields"}
      </button>
      {expanded && (
        <pre className="mt-1 rounded bg-[var(--muted)] p-2 text-xs font-mono overflow-x-auto max-w-md">
          {JSON.stringify(payload, null, 2)}
        </pre>
      )}
    </div>
  );
}
