"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { cn } from "@/shared/lib/cn";
import { closeForward, fxForwardsQueryOptions, rollForward } from "../api";
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

  const [rollTarget, setRollTarget] = useState<string | null>(null);
  const [newMaturityDate, setNewMaturityDate] = useState("");
  const [newContractRate, setNewContractRate] = useState("");
  const [currentSpot, setCurrentSpot] = useState("");

  const closeMutation = useMutation({
    mutationFn: ({
      forwardId,
      closeRate,
      closeSpot,
    }: {
      forwardId: string;
      closeRate: number | string;
      closeSpot: number | string;
    }) =>
      closeForward(fundSlug, forwardId, {
        close_rate: closeRate,
        close_spot: closeSpot,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fx-forwards"] });
      queryClient.invalidateQueries({ queryKey: ["fx-hedging-summary"] });
      toast.success("Forward closed");
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to close forward");
    },
  });

  const rollMutation = useMutation({
    mutationFn: ({
      forwardId,
      data,
    }: {
      forwardId: string;
      data: { new_maturity_date: string; new_contract_rate: string; current_spot: string };
    }) => rollForward(fundSlug, forwardId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fx-forwards"] });
      queryClient.invalidateQueries({ queryKey: ["fx-hedging-summary"] });
      toast.success("Forward rolled");
      setRollTarget(null);
      setNewMaturityDate("");
      setNewContractRate("");
      setCurrentSpot("");
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to roll forward");
    },
  });

  function handleRollSubmit() {
    if (!rollTarget || !newMaturityDate || !newContractRate || !currentSpot) return;
    rollMutation.mutate({
      forwardId: rollTarget,
      data: {
        new_maturity_date: newMaturityDate,
        new_contract_rate: newContractRate,
        current_spot: currentSpot,
      },
    });
  }

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading forwards...</div>;
  }

  if (!forwards || forwards.length === 0) {
    return (
      <div className="rounded-md border border-[var(--border)] p-8 text-center text-sm text-[var(--muted-foreground)]">
        No FX forward contracts found.
      </div>
    );
  }

  return (
    <>
      <div className="overflow-x-auto rounded-md border border-[var(--border)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--card)]">
              <th className="px-3 py-1.5 text-left font-medium text-[var(--muted-foreground)]">
                Pair
              </th>
              <th className="px-3 py-1.5 text-left font-medium text-[var(--muted-foreground)]">
                Dir
              </th>
              <th className="px-3 py-1.5 text-right font-medium text-[var(--muted-foreground)]">
                Notional
              </th>
              <th className="px-3 py-1.5 text-right font-medium text-[var(--muted-foreground)]">
                Rate
              </th>
              <th className="px-3 py-1.5 text-left font-medium text-[var(--muted-foreground)]">
                Maturity
              </th>
              <th className="px-3 py-1.5 text-right font-medium text-[var(--muted-foreground)]">
                MTM
              </th>
              <th className="px-3 py-1.5 text-left font-medium text-[var(--muted-foreground)]">
                Status
              </th>
              <th className="px-3 py-1.5 text-left font-medium text-[var(--muted-foreground)]">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {forwards.map((fwd) => (
              <ForwardRow
                key={fwd.id}
                forward={fwd}
                onClose={() =>
                  closeMutation.mutate({
                    forwardId: fwd.id,
                    closeRate: fwd.contract_rate,
                    closeSpot: fwd.spot_at_inception,
                  })
                }
                isClosing={closeMutation.isPending}
                onRoll={() => setRollTarget(fwd.id)}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Roll modal */}
      {rollTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-sm rounded-md border border-[var(--border)] bg-[var(--background)] p-6 shadow-lg">
            <h3 className="text-base font-semibold">Roll Forward</h3>
            <p className="mb-4 text-sm text-[var(--muted-foreground)]">
              Enter new terms for the rolled contract.
            </p>
            <div className="space-y-3">
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">
                  New Maturity Date
                </span>
                <input
                  type="date"
                  value={newMaturityDate}
                  onChange={(e) => setNewMaturityDate(e.target.value)}
                  className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">
                  New Contract Rate
                </span>
                <input
                  type="number"
                  step="0.0001"
                  value={newContractRate}
                  onChange={(e) => setNewContractRate(e.target.value)}
                  placeholder="1.0850"
                  className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">
                  Current Spot
                </span>
                <input
                  type="number"
                  step="0.0001"
                  value={currentSpot}
                  onChange={(e) => setCurrentSpot(e.target.value)}
                  placeholder="1.0800"
                  className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
                />
              </label>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setRollTarget(null);
                  setNewMaturityDate("");
                  setNewContractRate("");
                  setCurrentSpot("");
                }}
                className="rounded-md border border-[var(--border)] px-4 py-1.5 text-sm font-medium text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleRollSubmit}
                disabled={
                  !newMaturityDate || !newContractRate || !currentSpot || rollMutation.isPending
                }
                className="rounded-md bg-[var(--primary)] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
              >
                {rollMutation.isPending ? "Rolling..." : "Roll Forward"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function ForwardRow({
  forward,
  onClose,
  isClosing,
  onRoll,
}: {
  forward: FXForwardContract;
  onClose: () => void;
  isClosing: boolean;
  onRoll: () => void;
}) {
  const pair = `${forward.base_currency}/${forward.quote_currency}`;
  const mtmValue = forward.mtm_value ? Number(forward.mtm_value) : null;

  return (
    <tr className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--sidebar-active)]">
      <td className="px-3 py-1.5 font-medium">{pair}</td>
      <td className="px-3 py-1.5">
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
      <td className="px-3 py-1.5 text-right tabular-nums">{fmtAmount(forward.notional)}</td>
      <td className="px-3 py-1.5 text-right tabular-nums">{fmtRate(forward.contract_rate)}</td>
      <td className="px-3 py-1.5">{fmtDate(forward.maturity_date)}</td>
      <td className="px-3 py-1.5 text-right tabular-nums">
        {mtmValue !== null ? (
          <span className={mtmValue >= 0 ? "text-emerald-400" : "text-red-400"}>
            {fmtAmount(String(mtmValue))}
          </span>
        ) : (
          <span className="text-[var(--muted-foreground)]">--</span>
        )}
      </td>
      <td className="px-3 py-1.5">
        <span
          className={cn(
            "inline-block rounded-full px-2 py-0.5 text-xs font-medium",
            STATUS_STYLES[forward.status] ?? "",
          )}
        >
          {forward.status}
        </span>
      </td>
      <td className="px-3 py-1.5">
        {forward.status === "open" && (
          <div className="flex gap-1">
            <button
              type="button"
              onClick={onRoll}
              className="rounded px-2 py-1 text-xs font-medium text-blue-400 hover:bg-blue-400/10"
            >
              Roll
            </button>
            <button
              type="button"
              onClick={onClose}
              disabled={isClosing}
              className="rounded px-2 py-1 text-xs font-medium text-red-400 hover:bg-red-400/10 disabled:opacity-50"
            >
              Close
            </button>
          </div>
        )}
      </td>
    </tr>
  );
}
