"use client";

import { ArrowRightLeft, X } from "lucide-react";
import { useTradeTicket } from "@/shared/components/trade-ticket-provider";
import type { Instrument } from "../types";

interface InstrumentDetailPanelProps {
  instrument: Instrument;
  onClose: () => void;
}

export function InstrumentDetailPanel({ instrument, onClose }: InstrumentDetailPanelProps) {
  const { openTradeTicket } = useTradeTicket();

  const hasMarketData =
    instrument.annual_drift != null ||
    instrument.annual_volatility != null ||
    instrument.spread_bps != null;

  return (
    <div className="w-[340px] shrink-0 overflow-y-auto rounded-md border border-[var(--border)] bg-[var(--card)]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--border)] px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-semibold">{instrument.ticker}</span>
          <span className="rounded-full bg-[var(--muted)] px-2 py-0.5 text-[10px] font-medium">
            {instrument.asset_class}
          </span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Instrument info */}
      <div className="space-y-3 p-3">
        {/* Name */}
        <p className="text-xs font-medium text-[var(--foreground)]">{instrument.name}</p>

        {/* Core details */}
        <div className="grid grid-cols-2 gap-2">
          <DetailField label="Ticker" value={instrument.ticker} />
          <DetailField label="Asset Class" value={instrument.asset_class} />
          <DetailField label="Exchange" value={instrument.exchange} />
          <DetailField label="Currency" value={instrument.currency} />
          <DetailField label="Country" value={instrument.country || "—"} />
          <DetailField label="Sector" value={instrument.sector || "—"} />
          <DetailField label="Industry" value={instrument.industry || "—"} />
        </div>

        {/* Market data */}
        {hasMarketData && (
          <div>
            <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
              Market Data
            </p>
            <div className="grid grid-cols-2 gap-2 rounded-md border border-[var(--border)] bg-[var(--muted)] p-2">
              {instrument.annual_drift != null && (
                <DetailField
                  label="Annual Drift"
                  value={`${(instrument.annual_drift * 100).toFixed(2)}%`}
                />
              )}
              {instrument.annual_volatility != null && (
                <DetailField
                  label="Annual Volatility"
                  value={`${(instrument.annual_volatility * 100).toFixed(2)}%`}
                />
              )}
              {instrument.spread_bps != null && (
                <DetailField label="Spread" value={`${instrument.spread_bps} bps`} />
              )}
            </div>
          </div>
        )}

        {/* Trade action */}
        <div className="border-t border-[var(--border)] pt-3">
          <button
            type="button"
            onClick={() => openTradeTicket({ instrument: instrument.id })}
            className="inline-flex w-full items-center justify-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90"
          >
            <ArrowRightLeft className="h-3 w-3" />
            Trade
          </button>
        </div>
      </div>
    </div>
  );
}

function DetailField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] text-[var(--muted-foreground)]">{label}</p>
      <p className="font-mono text-xs font-medium">{value}</p>
    </div>
  );
}
