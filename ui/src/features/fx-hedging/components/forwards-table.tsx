"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { cn } from "@/shared/lib/cn";
import { closeForward, fxForwardsQueryOptions } from "../api";
import type { FXForwardContract } from "../types";

function fmtRate(value: string): string {
  return Number(value).toFixed(4);
}

function fmtAmount(value: string): string {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(Number(value));
}

function fmtDate(value: string): string {
  return new Date(value).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

const STATUS_STYLES: Record<string, string> = {
  open: "bg-emerald-400/10 text-emerald-400",
  closed: "bg-zinc-400/10 text-zinc-400",
  rolled: "bg-blue-400/10 text-blue-400",
  expired: "bg-amber-400/10 text-amber-400",
  settled: "bg-zinc-400/10 text-zinc-400",
};

export function ForwardsTable({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();
  const { data: forwards, isLoading } = useQuery(fxForwardsQueryOptions(fundSlug, portfolioId));

  const closeMutation = useMutation({
    mutationFn: (forwardId: string) => closeForward(fundSlug, { forward_id: forwardId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fx-forwards"] });
      queryClient.invalidateQueries({ queryKey: ["fx-hedging-summary"] });
    },
  });

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading forwards...</div>;
  }

  if (!forwards || forwards.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--border)] p-8 text-center text-sm text-[var(--muted-foreground)]">
        No FX forward contracts found.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--card)]">
            <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">Pair</th>
            <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">Dir</th>
            <th className="px-4 py-3 text-right font-medium text-[var(--muted-foreground)]">
              Notional
            </th>
            <th className="px-4 py-3 text-right font-medium text-[var(--muted-foreground)]">
              Rate
            </th>
            <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">
              Maturity
            </th>
            <th className="px-4 py-3 text-right font-medium text-[var(--muted-foreground)]">MTM</th>
            <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">
              Status
            </th>
            <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          {forwards.map((fwd) => (
            <ForwardRow
              key={fwd.id}
              forward={fwd}
              onClose={() => closeMutation.mutate(fwd.id)}
              isClosing={closeMutation.isPending}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ForwardRow({
  forward,
  onClose,
  isClosing,
}: {
  forward: FXForwardContract;
  onClose: () => void;
  isClosing: boolean;
}) {
  const pair = `${forward.base_currency}/${forward.quote_currency}`;
  const mtmValue = forward.mtm_value ? Number(forward.mtm_value) : null;

  return (
    <tr className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--sidebar-active)]">
      <td className="px-4 py-3 font-medium">{pair}</td>
      <td className="px-4 py-3">
        <span
          className={cn(
            "inline-block rounded px-1.5 py-0.5 text-xs font-medium",
            forward.direction === "buy"
              ? "bg-emerald-400/10 text-emerald-400"
              : "bg-red-400/10 text-red-400",
          )}
        >
          {forward.direction.toUpperCase()}
        </span>
      </td>
      <td className="px-4 py-3 text-right tabular-nums">{fmtAmount(forward.notional)}</td>
      <td className="px-4 py-3 text-right tabular-nums">{fmtRate(forward.contract_rate)}</td>
      <td className="px-4 py-3">{fmtDate(forward.maturity_date)}</td>
      <td className="px-4 py-3 text-right tabular-nums">
        {mtmValue !== null ? (
          <span className={mtmValue >= 0 ? "text-emerald-400" : "text-red-400"}>
            {fmtAmount(String(mtmValue))}
          </span>
        ) : (
          <span className="text-[var(--muted-foreground)]">--</span>
        )}
      </td>
      <td className="px-4 py-3">
        <span
          className={cn(
            "inline-block rounded-full px-2 py-0.5 text-xs font-medium",
            STATUS_STYLES[forward.status] ?? "",
          )}
        >
          {forward.status}
        </span>
      </td>
      <td className="px-4 py-3">
        {forward.status === "open" && (
          <button
            type="button"
            onClick={onClose}
            disabled={isClosing}
            className="rounded px-2 py-1 text-xs font-medium text-red-400 hover:bg-red-400/10 disabled:opacity-50"
          >
            Close
          </button>
        )}
      </td>
    </tr>
  );
}
