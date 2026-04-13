"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { WaterfallChart } from "@/shared/components/charts";
import { InstrumentLink } from "@/shared/components/instrument-link";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { brinsonFachlerQueryOptions } from "../api";
import type { SectorAttribution } from "../types";
import { ActiveReturnWaterfall } from "./active-return-waterfall";

interface Props {
  portfolioId: string;
  start: string;
  end: string;
}

function pct(v: string): string {
  return `${(parseFloat(v) * 100).toFixed(2)}%`;
}

export function BrinsonFachlerTable({ portfolioId, start, end }: Props) {
  const { fundSlug } = useFundContext();
  const { data, isLoading } = useQuery(
    brinsonFachlerQueryOptions(fundSlug, portfolioId, start, end),
  );
  const [expandedSector, setExpandedSector] = useState<string | null>(null);

  const waterfallItems = useMemo(() => {
    if (!data) return [];
    return [
      { label: "Allocation", value: parseFloat(data.total_allocation) },
      { label: "Selection", value: parseFloat(data.total_selection) },
      { label: "Interaction", value: parseFloat(data.total_interaction) },
      { label: "Active", value: parseFloat(data.active_return), isTotal: true },
    ];
  }, [data]);

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading attribution...</div>;
  }

  if (!data?.sectors) return null;

  return (
    <div className="space-y-2">
      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-2">
        <SummaryCard label="Portfolio Return" value={pct(data.portfolio_return)} />
        <SummaryCard label="Benchmark Return" value={pct(data.benchmark_return)} />
        <SummaryCard
          label="Active Return"
          value={pct(data.active_return)}
          highlight={parseFloat(data.active_return) > 0 ? "success" : "destructive"}
        />
      </div>

      {/* Waterfall chart */}
      <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
        <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          Attribution Decomposition
        </p>
        <WaterfallChart
          items={waterfallItems}
          height={180}
          formatValue={(v) => `${(v * 100).toFixed(2)}%`}
        />
      </div>

      {/* Active return waterfall by sector */}
      <ActiveReturnWaterfall data={data} />

      {/* Contribution cards */}
      <div className="grid grid-cols-3 gap-2">
        <SummaryCard label="Total Allocation" value={pct(data.total_allocation)} />
        <SummaryCard label="Total Selection" value={pct(data.total_selection)} />
        <SummaryCard label="Total Interaction" value={pct(data.total_interaction)} />
      </div>

      {/* Sector detail table */}
      <div className="overflow-x-auto rounded-md border border-[var(--border)] bg-[var(--card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)] text-left text-xs text-[var(--muted-foreground)]">
              <th className="px-3 py-1 font-medium">Sector</th>
              <th className="px-3 py-1 font-medium text-right">Port Weight</th>
              <th className="px-3 py-1 font-medium text-right">Bench Weight</th>
              <th className="px-3 py-1 font-medium text-right">Port Return</th>
              <th className="px-3 py-1 font-medium text-right">Bench Return</th>
              <th className="px-3 py-1 font-medium text-right">Allocation</th>
              <th className="px-3 py-1 font-medium text-right">Selection</th>
              <th className="px-3 py-1 font-medium text-right">Interaction</th>
              <th className="px-3 py-1 font-medium text-right">Total</th>
            </tr>
          </thead>
          <tbody>
            {data.sectors.map((s) => {
              const isExpanded = expandedSector === s.sector;
              const hasInstruments = !!(s.instruments && s.instruments.length > 0);
              return (
                <SectorRow
                  key={s.sector}
                  sector={s}
                  isExpanded={isExpanded}
                  hasInstruments={hasInstruments}
                  onToggle={() => setExpandedSector(isExpanded ? null : s.sector)}
                />
              );
            })}
            {data.sectors.length === 0 && (
              <tr>
                <td colSpan={9} className="px-3 py-4 text-center text-[var(--muted-foreground)]">
                  No sector data for this period.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SectorRow({
  sector,
  isExpanded,
  hasInstruments,
  onToggle,
}: {
  sector: SectorAttribution;
  isExpanded: boolean;
  hasInstruments: boolean;
  onToggle: () => void;
}) {
  const totalEffect = parseFloat(sector.total_effect);

  return (
    <>
      <tr
        className={`border-b border-[var(--border)] last:border-0 ${hasInstruments ? "cursor-pointer" : ""} ${isExpanded ? "bg-[var(--table-row-hover)]" : "hover:bg-[var(--table-row-hover)]"}`}
        onClick={hasInstruments ? onToggle : undefined}
      >
        <td className="px-3 py-1 font-medium">
          <span className="flex items-center gap-1">
            {hasInstruments && (
              <span
                className="inline-block w-3 text-[10px] text-[var(--muted-foreground)] transition-transform"
                style={{ transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)" }}
              >
                &#9654;
              </span>
            )}
            {sector.sector}
          </span>
        </td>
        <td className="px-3 py-2 text-right font-mono">{pct(sector.portfolio_weight)}</td>
        <td className="px-3 py-2 text-right font-mono">{pct(sector.benchmark_weight)}</td>
        <td className="px-3 py-2 text-right font-mono">{pct(sector.portfolio_return)}</td>
        <td className="px-3 py-2 text-right font-mono">{pct(sector.benchmark_return)}</td>
        <td className="px-3 py-2 text-right font-mono">{pct(sector.allocation_effect)}</td>
        <td className="px-3 py-2 text-right font-mono">{pct(sector.selection_effect)}</td>
        <td className="px-3 py-2 text-right font-mono">{pct(sector.interaction_effect)}</td>
        <td
          className="px-3 py-2 text-right font-mono font-semibold"
          style={{
            color:
              totalEffect > 0
                ? "var(--success)"
                : totalEffect < 0
                  ? "var(--destructive)"
                  : undefined,
          }}
        >
          {pct(sector.total_effect)}
        </td>
      </tr>
      {isExpanded && hasInstruments && (
        <>
          {sector.instruments?.map((inst) => {
            const contribution = parseFloat(inst.contribution);
            return (
              <tr
                key={inst.instrument_id}
                className="border-b border-[var(--table-border)] bg-[var(--table-header)] last:border-b-0"
              >
                <td className="py-1 pl-7 pr-3">
                  <InstrumentLink instrument={inst.instrument_id} />
                </td>
                <td className="px-3 py-1 text-right font-mono text-[var(--muted-foreground)]">
                  {pct(inst.portfolio_weight)}
                </td>
                <td className="px-3 py-1 text-right font-mono text-[var(--muted-foreground)]">
                  {pct(inst.benchmark_weight)}
                </td>
                <td className="px-3 py-1 text-right font-mono text-[var(--muted-foreground)]">
                  {pct(inst.portfolio_return)}
                </td>
                <td className="px-3 py-1 text-right font-mono text-[var(--muted-foreground)]">
                  {pct(inst.benchmark_return)}
                </td>
                {/* Span across allocation/selection/interaction columns */}
                <td colSpan={3} />
                <td
                  className="px-3 py-1 text-right font-mono text-xs"
                  style={{
                    color:
                      contribution > 0
                        ? "var(--success)"
                        : contribution < 0
                          ? "var(--destructive)"
                          : undefined,
                  }}
                >
                  {pct(inst.contribution)}
                </td>
              </tr>
            );
          })}
        </>
      )}
    </>
  );
}

function SummaryCard({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: "success" | "destructive";
}) {
  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
      <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
      <p
        className="mt-0.5 font-mono text-sm font-semibold"
        style={highlight ? { color: `var(--${highlight})` } : undefined}
      >
        {value}
      </p>
    </div>
  );
}
