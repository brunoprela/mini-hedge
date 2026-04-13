"use client";

import { useQuery } from "@tanstack/react-query";
import { orderFillsQueryOptions } from "@/features/orders/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import type { TCAReport } from "../types";

/**
 * Execution Timeline Chart — plots fill prices against an interpolated market
 * price line over the execution window. Fills are colored green when favorable
 * (below market for buys, above for sells) and red otherwise. A dashed VWAP
 * reference line is shown when available.
 */

// ─── Helpers ───────────────────────────────────────────────

function fmtPrice(v: number): string {
  return v.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  });
}

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

// ─── Component ─────────────────────────────────────────────

interface ExecutionTimelineChartProps {
  orderId: string;
  report: TCAReport;
}

export function ExecutionTimelineChart({ orderId, report }: ExecutionTimelineChartProps) {
  const { fundSlug } = useFundContext();
  const { data: fills } = useQuery(orderFillsQueryOptions(fundSlug, orderId));

  if (!fills || fills.length === 0) {
    return (
      <p className="text-sm text-[var(--muted-foreground)]">
        No fill data available for execution timeline.
      </p>
    );
  }

  const isBuy = report.side === "buy";
  const arrivalPrice = parseFloat(report.arrival_price);
  const vwap = parseFloat(report.vwap);
  const avgFillPrice = parseFloat(report.avg_fill_price);

  // Sort fills chronologically
  const sorted = [...fills].sort(
    (a, b) => new Date(a.filled_at).getTime() - new Date(b.filled_at).getTime(),
  );

  const firstTime = new Date(sorted[0].filled_at).getTime();
  const lastTime = new Date(sorted[sorted.length - 1].filled_at).getTime();
  const timeSpan = lastTime - firstTime || 1; // avoid division by zero

  // Fill data points
  const fillPoints = sorted.map((f) => ({
    t: new Date(f.filled_at).getTime(),
    price: parseFloat(f.price),
    quantity: parseFloat(f.quantity),
    timestamp: f.filled_at,
  }));

  // Market price line: interpolate from arrival price at first fill to avg fill price at last fill.
  // This is an approximation — in production you'd have real market tick data.
  const marketStart = arrivalPrice;
  const marketEnd = avgFillPrice;

  // Compute price range for Y axis
  const allPrices = [
    ...fillPoints.map((f) => f.price),
    marketStart,
    marketEnd,
    vwap,
  ];
  const minPrice = Math.min(...allPrices);
  const maxPrice = Math.max(...allPrices);
  const priceRange = maxPrice - minPrice || 1;
  const padding = priceRange * 0.15;
  const yMin = minPrice - padding;
  const yMax = maxPrice + padding;
  const yRange = yMax - yMin;

  // SVG dimensions
  const viewW = 600;
  const height = 240;
  const padTop = 20;
  const padBot = 32;
  const padLeft = 60;
  const padRight = 16;
  const chartW = viewW - padLeft - padRight;
  const chartH = height - padTop - padBot;

  function toX(t: number): number {
    if (timeSpan === 0) return padLeft + chartW / 2;
    return padLeft + ((t - firstTime) / timeSpan) * chartW;
  }

  function toY(price: number): number {
    return padTop + chartH - ((price - yMin) / yRange) * chartH;
  }

  // Market line points (just start → end)
  const marketLinePoints = `${toX(firstTime)},${toY(marketStart)} ${toX(lastTime)},${toY(marketEnd)}`;

  // Interpolated market price at a given time
  function marketPriceAt(t: number): number {
    const pct = timeSpan === 0 ? 0.5 : (t - firstTime) / timeSpan;
    return marketStart + (marketEnd - marketStart) * pct;
  }

  // Y-axis ticks (5 ticks)
  const yTicks = Array.from({ length: 5 }, (_, i) => yMin + (yRange * i) / 4);

  // X-axis labels — show a few fill timestamps
  const xLabelCount = Math.min(fillPoints.length, 6);
  const xLabelIndices: number[] = [];
  if (fillPoints.length <= xLabelCount) {
    fillPoints.forEach((_, i) => xLabelIndices.push(i));
  } else {
    for (let i = 0; i < xLabelCount; i++) {
      xLabelIndices.push(Math.round((i / (xLabelCount - 1)) * (fillPoints.length - 1)));
    }
  }

  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
      <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
        Execution Timeline
      </p>

      <svg
        viewBox={`0 0 ${viewW} ${height}`}
        className="w-full"
        preserveAspectRatio="xMidYMid meet"
      >
        <title>Execution Timeline — fill prices vs market</title>

        {/* Y-axis grid + labels */}
        {yTicks.map((tick) => (
          <g key={tick}>
            <line
              x1={padLeft}
              x2={viewW - padRight}
              y1={toY(tick)}
              y2={toY(tick)}
              stroke="var(--border)"
              strokeWidth={0.5}
            />
            <text
              x={padLeft - 6}
              y={toY(tick) + 3}
              textAnchor="end"
              fontSize={9}
              fontFamily="monospace"
              fill="var(--muted-foreground)"
            >
              {fmtPrice(tick)}
            </text>
          </g>
        ))}

        {/* VWAP reference line */}
        {!Number.isNaN(vwap) && vwap > 0 && (
          <g>
            <line
              x1={padLeft}
              x2={viewW - padRight}
              y1={toY(vwap)}
              y2={toY(vwap)}
              stroke="var(--muted-foreground)"
              strokeWidth={1}
              strokeDasharray="6,4"
              opacity={0.6}
            />
            <text
              x={viewW - padRight + 2}
              y={toY(vwap) + 3}
              fontSize={8}
              fill="var(--muted-foreground)"
            >
              VWAP
            </text>
          </g>
        )}

        {/* Market price line */}
        <polyline
          points={marketLinePoints}
          fill="none"
          stroke="var(--primary)"
          strokeWidth={1.5}
          strokeLinecap="round"
        />

        {/* Fill dots */}
        {fillPoints.map((fp, i) => {
          const marketPx = marketPriceAt(fp.t);
          // Favorable: buy below market, sell above market
          const favorable = isBuy ? fp.price <= marketPx : fp.price >= marketPx;
          const color = favorable ? "var(--success)" : "var(--destructive)";
          // Scale dot size by relative quantity
          const maxQty = Math.max(...fillPoints.map((f) => f.quantity));
          const minR = 3;
          const maxR = 7;
          const r = maxQty > 0 ? minR + ((fp.quantity / maxQty) * (maxR - minR)) : 4;

          return (
            <g key={fp.timestamp + String(i)}>
              {/* Vertical line from market to fill */}
              <line
                x1={toX(fp.t)}
                x2={toX(fp.t)}
                y1={toY(marketPx)}
                y2={toY(fp.price)}
                stroke={color}
                strokeWidth={0.75}
                strokeDasharray="2,2"
                opacity={0.5}
              />
              <circle
                cx={toX(fp.t)}
                cy={toY(fp.price)}
                r={r}
                fill={color}
                opacity={0.85}
              />
            </g>
          );
        })}

        {/* X-axis labels */}
        {xLabelIndices.map((idx) => {
          const fp = fillPoints[idx];
          return (
            <text
              key={`x-${idx}`}
              x={toX(fp.t)}
              y={height - 4}
              textAnchor="middle"
              fontSize={8}
              fill="var(--muted-foreground)"
            >
              {fmtTime(fp.timestamp)}
            </text>
          );
        })}

        {/* Legend */}
        <g>
          {/* Market line */}
          <line
            x1={padLeft}
            x2={padLeft + 16}
            y1={8}
            y2={8}
            stroke="var(--primary)"
            strokeWidth={2}
          />
          <text x={padLeft + 20} y={11} fontSize={9} fill="var(--muted-foreground)">
            Market
          </text>

          {/* Favorable fill */}
          <circle cx={padLeft + 82} cy={8} r={3.5} fill="var(--success)" />
          <text x={padLeft + 89} y={11} fontSize={9} fill="var(--muted-foreground)">
            Favorable
          </text>

          {/* Unfavorable fill */}
          <circle cx={padLeft + 152} cy={8} r={3.5} fill="var(--destructive)" />
          <text x={padLeft + 159} y={11} fontSize={9} fill="var(--muted-foreground)">
            Unfavorable
          </text>

          {/* VWAP */}
          <line
            x1={padLeft + 230}
            x2={padLeft + 246}
            y1={8}
            y2={8}
            stroke="var(--muted-foreground)"
            strokeWidth={1}
            strokeDasharray="4,2"
          />
          <text x={padLeft + 250} y={11} fontSize={9} fill="var(--muted-foreground)">
            VWAP
          </text>
        </g>
      </svg>
    </div>
  );
}
