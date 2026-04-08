"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { feeScheduleQueryOptions, updateFeeSchedule } from "../api";
import type { FeeScheduleResponse } from "../types";

const CRYSTALLIZATION_OPTIONS = ["annual", "quarterly", "semi-annual", "monthly"] as const;
const PAYMENT_OPTIONS = ["quarterly", "monthly", "semi-annual", "annual"] as const;

interface EditFormData {
  bps: number;
  perfPct: number;
  hurdlePct: number;
  hwm: boolean;
  crystal: string;
  payment: string;
}

function initFormData(schedule: FeeScheduleResponse): EditFormData {
  return {
    bps: schedule.management_fee_bps,
    perfPct: Number((Number(schedule.performance_fee_pct) * 100).toFixed(2)),
    hurdlePct: Number((Number(schedule.hurdle_rate_pct) * 100).toFixed(2)),
    hwm: schedule.high_water_mark,
    crystal: schedule.crystallization_frequency,
    payment: schedule.payment_frequency,
  };
}

function EditDialog({
  schedule,
  onClose,
}: {
  schedule: FeeScheduleResponse;
  onClose: () => void;
}) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<EditFormData>(() => initFormData(schedule));

  const mutation = useMutation({
    mutationFn: () =>
      updateFeeSchedule(fundSlug, {
        management_fee_bps: form.bps,
        performance_fee_pct: form.perfPct / 100,
        hurdle_rate_pct: form.hurdlePct / 100,
        high_water_mark: form.hwm,
        crystallization_frequency: form.crystal,
        payment_frequency: form.payment,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fee-schedule"] });
      toast.success("Fee schedule updated");
      onClose();
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const inputClass =
    "w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm";
  const labelClass = "mb-1 block text-sm text-[var(--muted-foreground)]";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-md border border-[var(--border)] bg-[var(--background)] p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Edit Fee Schedule</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            &times;
          </button>
        </div>

        <div className="space-y-3">
          <div>
            <label htmlFor="fee-bps" className={labelClass}>
              Management Fee (bps)
            </label>
            <input
              id="fee-bps"
              type="number"
              min="0"
              step="1"
              value={form.bps}
              onChange={(e) => setForm((f) => ({ ...f, bps: Number(e.target.value) }))}
              className={inputClass}
            />
          </div>

          <div>
            <label htmlFor="fee-perf" className={labelClass}>
              Performance Fee (%)
            </label>
            <input
              id="fee-perf"
              type="number"
              min="0"
              max="100"
              step="0.1"
              value={form.perfPct}
              onChange={(e) => setForm((f) => ({ ...f, perfPct: Number(e.target.value) }))}
              className={inputClass}
            />
          </div>

          <div>
            <label htmlFor="fee-hurdle" className={labelClass}>
              Hurdle Rate (%)
            </label>
            <input
              id="fee-hurdle"
              type="number"
              min="0"
              max="100"
              step="0.1"
              value={form.hurdlePct}
              onChange={(e) => setForm((f) => ({ ...f, hurdlePct: Number(e.target.value) }))}
              className={inputClass}
            />
          </div>

          <div className="flex items-center gap-2">
            <input
              id="fee-hwm"
              type="checkbox"
              checked={form.hwm}
              onChange={(e) => setForm((f) => ({ ...f, hwm: e.target.checked }))}
              className="h-4 w-4 rounded border-[var(--border)]"
            />
            <label htmlFor="fee-hwm" className="text-sm">
              High Water Mark
            </label>
          </div>

          <div>
            <label htmlFor="fee-crystal" className={labelClass}>
              Crystallization
            </label>
            <select
              id="fee-crystal"
              value={form.crystal}
              onChange={(e) => setForm((f) => ({ ...f, crystal: e.target.value }))}
              className={inputClass}
            >
              {CRYSTALLIZATION_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt.charAt(0).toUpperCase() + opt.slice(1)}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="fee-payment" className={labelClass}>
              Payment
            </label>
            <select
              id="fee-payment"
              value={form.payment}
              onChange={(e) => setForm((f) => ({ ...f, payment: e.target.value }))}
              className={inputClass}
            >
              {PAYMENT_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt.charAt(0).toUpperCase() + opt.slice(1)}
                </option>
              ))}
            </select>
          </div>

          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 rounded-md border border-[var(--border)] py-2 text-sm"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className="flex-1 rounded-md bg-[var(--foreground)] py-2 text-sm font-medium text-[var(--background)] transition-colors hover:opacity-90 disabled:opacity-50"
            >
              {mutation.isPending ? "Saving..." : "Save"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function FeeScheduleCard() {
  const { fundSlug } = useFundContext();
  const { data: schedule, isLoading } = useQuery(feeScheduleQueryOptions(fundSlug));
  const [editing, setEditing] = useState(false);

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading fee schedule...</div>;
  }

  if (!schedule) {
    return (
      <div className="rounded-md border border-[var(--border)] p-6 text-center text-sm text-[var(--muted-foreground)]">
        No fee schedule configured for this fund.
      </div>
    );
  }

  const items = [
    { label: "Management Fee", value: `${schedule.management_fee_bps} bps` },
    {
      label: "Performance Fee",
      value: `${(Number(schedule.performance_fee_pct) * 100).toFixed(1)}%`,
    },
    { label: "Hurdle Rate", value: `${(Number(schedule.hurdle_rate_pct) * 100).toFixed(1)}%` },
    { label: "High Water Mark", value: schedule.high_water_mark ? "Yes" : "No" },
    { label: "Crystallization", value: schedule.crystallization_frequency },
    { label: "Payment", value: schedule.payment_frequency },
  ];

  return (
    <div className="rounded-md border border-[var(--border)] p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Fee Schedule</h3>
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="rounded-md border border-[var(--border)] px-2 py-1 text-xs text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
        >
          Edit
        </button>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {items.map((item) => (
          <div key={item.label}>
            <p className="text-xs text-[var(--muted-foreground)]">{item.label}</p>
            <p className="text-sm font-medium">{item.value}</p>
          </div>
        ))}
      </div>
      {editing && <EditDialog schedule={schedule} onClose={() => setEditing(false)} />}
    </div>
  );
}
