"use client";

import type { SettlementRecord } from "../types";

// ─── Types ─────────────────────────────────────────────────

export interface SettlementEvent {
  id: string;
  instrument: string;
  quantity: number;
  trade_date: string;
  settlement_date: string;
  status: "pending" | "settled" | "failed";
  counterparty?: string;
  amount: number;
}

// ─── Helpers ───────────────────────────────────────────────

function toDate(s: string): Date {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function fmtShortDate(d: Date): string {
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${months[d.getMonth()]} ${d.getDate()}`;
}

function daysBetween(a: Date, b: Date): number {
  return Math.round((b.getTime() - a.getTime()) / (1000 * 60 * 60 * 24));
}

/** Generate an array of business days starting from a date. */
function businessDays(start: Date, count: number): Date[] {
  const result: Date[] = [];
  const current = new Date(start);
  while (result.length < count) {
    const dow = current.getDay();
    if (dow !== 0 && dow !== 6) {
      result.push(new Date(current));
    }
    current.setDate(current.getDate() + 1);
  }
  return result;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "var(--warning)",
  settled: "var(--success)",
  failed: "var(--destructive)",
  cancelled: "var(--muted-foreground)",
};

const STATUS_OPACITY: Record<string, number> = {
  pending: 0.85,
  settled: 0.7,
  failed: 0.9,
  cancelled: 0.4,
};

// ─── Convert API records to SettlementEvents ───────────────

export function recordsToEvents(
  records: SettlementRecord[],
  instrumentMap: Map<string, string>,
): SettlementEvent[] {
  return records
    .filter((r) => r.status !== "cancelled")
    .map((r) => ({
      id: r.id,
      instrument: instrumentMap.get(r.instrument_id) ?? r.instrument_id.slice(0, 8),
      quantity: 0, // not available on SettlementRecord
      trade_date: r.trade_date,
      settlement_date: r.settlement_date,
      status: r.status as "pending" | "settled" | "failed",
      amount: Number(r.settlement_amount),
    }));
}

// ─── Gantt Chart Component ─────────────────────────────────

interface SettlementGanttProps {
  events: SettlementEvent[];
}

export function SettlementGantt({ events }: SettlementGanttProps) {
  if (events.length === 0) {
    return <p className="text-xs text-[var(--muted-foreground)]">No settlement events to display.</p>;
  }

  // Determine timeline range: earliest trade_date to latest settlement_date
  const allDates = events.flatMap((e) => [toDate(e.trade_date), toDate(e.settlement_date)]);
  const minDate = new Date(Math.min(...allDates.map((d) => d.getTime())));
  const maxDate = new Date(Math.max(...allDates.map((d) => d.getTime())));

  // Extend range slightly for padding
  const rangeStart = new Date(minDate);
  rangeStart.setDate(rangeStart.getDate() - 1);
  const rangeEnd = new Date(maxDate);
  rangeEnd.setDate(rangeEnd.getDate() + 1);

  const totalDays = Math.max(daysBetween(rangeStart, rangeEnd), 1);

  // Generate column dates for the header (all calendar days in range)
  const columnDates: Date[] = [];
  {
    const cur = new Date(rangeStart);
    while (cur <= rangeEnd) {
      columnDates.push(new Date(cur));
      cur.setDate(cur.getDate() + 1);
    }
  }

  // Sort events: pending first, then by settlement_date
  const sorted = [...events].sort((a, b) => {
    const statusOrder = { failed: 0, pending: 1, settled: 2 };
    const sa = statusOrder[a.status] ?? 1;
    const sb = statusOrder[b.status] ?? 1;
    if (sa !== sb) return sa - sb;
    return toDate(a.settlement_date).getTime() - toDate(b.settlement_date).getTime();
  });

  // Layout constants
  const labelW = 120;
  const amountW = 80;
  const padRight = 8;
  const rowH = 26;
  const headerH = 32;
  const viewW = 700;
  const chartW = viewW - labelW - amountW - padRight;
  const totalH = headerH + sorted.length * rowH + 4;

  function dayToX(date: Date): number {
    const d = daysBetween(rangeStart, date);
    return labelW + (d / totalDays) * chartW;
  }

  const fmtAmount = (v: number) =>
    v.toLocaleString("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    });

  // Today marker
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const showToday = today >= rangeStart && today <= rangeEnd;

  return (
    <div className="overflow-x-auto">
      <svg
        viewBox={`0 0 ${viewW} ${totalH}`}
        className="w-full min-w-[600px]"
        preserveAspectRatio="xMidYMin meet"
      >
        <title>Settlement Ladder Timeline</title>

        {/* Column date headers */}
        {columnDates.map((d) => {
          const x = dayToX(d);
          const isWeekend = d.getDay() === 0 || d.getDay() === 6;
          return (
            <g key={d.toISOString()}>
              {/* Vertical gridline */}
              <line
                x1={x}
                x2={x}
                y1={headerH}
                y2={totalH}
                stroke="var(--border)"
                strokeWidth={0.5}
                opacity={isWeekend ? 0.3 : 0.6}
              />
              {/* Weekend shading */}
              {isWeekend && (
                <rect
                  x={x}
                  y={headerH}
                  width={chartW / totalDays}
                  height={totalH - headerH}
                  fill="var(--muted-foreground)"
                  opacity={0.04}
                />
              )}
              {/* Date label (skip weekends to reduce clutter) */}
              {!isWeekend && (
                <text
                  x={x + (chartW / totalDays) / 2}
                  y={14}
                  textAnchor="middle"
                  fontSize={8}
                  fill="var(--muted-foreground)"
                >
                  {fmtShortDate(d)}
                </text>
              )}
            </g>
          );
        })}

        {/* Header separator */}
        <line
          x1={0}
          x2={viewW}
          y1={headerH}
          y2={headerH}
          stroke="var(--border)"
          strokeWidth={1}
        />

        {/* Today marker */}
        {showToday && (
          <>
            <line
              x1={dayToX(today)}
              x2={dayToX(today)}
              y1={headerH}
              y2={totalH}
              stroke="var(--primary)"
              strokeWidth={1}
              strokeDasharray="4,3"
              opacity={0.6}
            />
            <text
              x={dayToX(today)}
              y={headerH - 4}
              textAnchor="middle"
              fontSize={7}
              fontWeight={600}
              fill="var(--primary)"
            >
              TODAY
            </text>
          </>
        )}

        {/* Rows */}
        {sorted.map((event, i) => {
          const y = headerH + i * rowH;
          const tradeX = dayToX(toDate(event.trade_date));
          const settleX = dayToX(toDate(event.settlement_date));
          const barW = Math.max(settleX - tradeX, 4);
          const barH = 16;
          const barY = y + (rowH - barH) / 2;
          const color = STATUS_COLORS[event.status] ?? "var(--muted-foreground)";
          const opacity = STATUS_OPACITY[event.status] ?? 0.7;

          return (
            <g key={event.id}>
              {/* Row stripe */}
              {i % 2 === 0 && (
                <rect
                  x={0}
                  y={y}
                  width={viewW}
                  height={rowH}
                  fill="var(--muted-foreground)"
                  opacity={0.03}
                />
              )}

              {/* Row separator */}
              <line
                x1={0}
                x2={viewW}
                y1={y + rowH}
                y2={y + rowH}
                stroke="var(--border)"
                strokeWidth={0.3}
              />

              {/* Instrument label */}
              <text
                x={4}
                y={y + rowH / 2 + 3}
                fontSize={10}
                fontFamily="monospace"
                fontWeight={500}
                fill="var(--foreground)"
              >
                {event.instrument}
              </text>

              {/* Status dot */}
              <circle
                cx={labelW - 14}
                cy={y + rowH / 2}
                r={3}
                fill={color}
                opacity={opacity}
              />

              {/* Bar: trade_date -> settlement_date */}
              <rect
                x={tradeX}
                y={barY}
                width={barW}
                height={barH}
                rx={3}
                fill={color}
                opacity={opacity}
              />

              {/* Bar label (ticker + counterparty inside bar if wide enough) */}
              {barW > 50 && (
                <text
                  x={tradeX + 4}
                  y={barY + barH / 2 + 3}
                  fontSize={8}
                  fontFamily="monospace"
                  fill="var(--card)"
                  fontWeight={600}
                >
                  {event.counterparty ?? event.instrument}
                </text>
              )}

              {/* Amount label (right side) */}
              <text
                x={viewW - padRight}
                y={y + rowH / 2 + 3}
                textAnchor="end"
                fontSize={9}
                fontFamily="monospace"
                fill={Number(event.amount) >= 0 ? "var(--success)" : "var(--destructive)"}
              >
                {fmtAmount(event.amount)}
              </text>
            </g>
          );
        })}

        {/* Legend */}
        {[
          { label: "Pending", color: STATUS_COLORS.pending },
          { label: "Settled", color: STATUS_COLORS.settled },
          { label: "Failed", color: STATUS_COLORS.failed },
        ].map((item, i) => (
          <g key={item.label}>
            <rect
              x={labelW + i * 80}
              y={headerH - 28}
              width={10}
              height={10}
              rx={2}
              fill={item.color}
              opacity={0.8}
            />
            <text
              x={labelW + i * 80 + 14}
              y={headerH - 20}
              fontSize={8}
              fill="var(--muted-foreground)"
            >
              {item.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
