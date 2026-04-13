"use client";

import type { OrderIntent } from "../types";

/**
 * Horizontal Gantt-style timeline for order intents.
 * Pure SVG — no external chart dependencies.
 *
 * Since the API OrderIntent does not carry timestamps, we generate
 * synthetic execution windows: each intent starts at "now" and
 * stretches proportionally to its estimated_value (larger trades
 * take longer to execute). This gives a visual sense of the
 * execution schedule the desk would follow.
 */

interface OrderIntentGanttProps {
  intents: OrderIntent[];
}

export function OrderIntentGantt({ intents }: OrderIntentGanttProps) {
  if (intents.length === 0) {
    return (
      <p className="text-xs text-[var(--muted-foreground)]">
        No order intents to display on timeline.
      </p>
    );
  }

  // ── Layout constants ───────────────────────────────────────
  const labelW = 90;
  const padRight = 16;
  const padTop = 20;
  const rowH = 24;
  const barH = 14;
  const viewW = 600;
  const chartW = viewW - labelW - padRight;
  const chartH = intents.length * rowH + padTop + 12;

  // ── Time axis ──────────────────────────────────────────────
  // Build a synthetic timeline: 6 hours from "now".
  const now = new Date();
  const windowHours = 6;
  const timeStart = now.getTime();
  const timeEnd = timeStart + windowHours * 60 * 60 * 1000;
  const timeRange = timeEnd - timeStart;

  // Estimate execution duration per intent (proportional to value).
  const values = intents.map((i) => Math.abs(Number.parseFloat(i.estimated_value) || 1));
  const maxValue = Math.max(...values);

  // Each bar starts staggered and has a duration proportional to value.
  const bars = intents.map((intent, idx) => {
    const value = values[idx];
    // Stagger starts across the first 40% of the window
    const staggerOffset = (idx / Math.max(intents.length - 1, 1)) * timeRange * 0.35;
    const start = timeStart + staggerOffset;
    // Duration: 15 min to 3 hours, proportional to value
    const minDur = 15 * 60 * 1000;
    const maxDur = 3 * 60 * 60 * 1000;
    const duration = minDur + (value / maxValue) * (maxDur - minDur);
    const end = Math.min(start + duration, timeEnd);
    return { intent, start, end };
  });

  function toX(ts: number) {
    return labelW + ((ts - timeStart) / timeRange) * chartW;
  }

  // X-axis hour ticks
  const hourTicks: { label: string; x: number }[] = [];
  for (let h = 0; h <= windowHours; h++) {
    const ts = timeStart + h * 60 * 60 * 1000;
    const d = new Date(ts);
    const hh = d.getHours().toString().padStart(2, "0");
    const mm = d.getMinutes().toString().padStart(2, "0");
    hourTicks.push({ label: `${hh}:${mm}`, x: toX(ts) });
  }

  // "Now" marker
  const nowX = toX(now.getTime());

  return (
    <svg
      viewBox={`0 0 ${viewW} ${chartH}`}
      className="w-full"
      preserveAspectRatio="xMidYMid meet"
    >
      <title>Order Intent Gantt Timeline</title>

      {/* ── Grid lines (vertical at each hour) ─────────────── */}
      {hourTicks.map((tick) => (
        <g key={tick.label}>
          <line
            x1={tick.x}
            x2={tick.x}
            y1={padTop}
            y2={chartH - 12}
            stroke="var(--border)"
            strokeWidth={0.5}
          />
          <text
            x={tick.x}
            y={padTop - 6}
            textAnchor="middle"
            fontSize={8}
            fill="var(--muted-foreground)"
          >
            {tick.label}
          </text>
        </g>
      ))}

      {/* ── "Now" marker ───────────────────────────────────── */}
      <line
        x1={nowX}
        x2={nowX}
        y1={padTop}
        y2={chartH - 12}
        stroke="var(--foreground)"
        strokeWidth={1}
        strokeDasharray="4,3"
        opacity={0.6}
      />
      <text
        x={nowX}
        y={padTop - 1}
        textAnchor="middle"
        fontSize={7}
        fontWeight={600}
        fill="var(--foreground)"
      >
        NOW
      </text>

      {/* ── Defs for striped pattern ───────────────────────── */}
      <defs>
        <pattern
          id="gantt-stripe"
          patternUnits="userSpaceOnUse"
          width={6}
          height={6}
          patternTransform="rotate(45)"
        >
          <line
            x1={0}
            y1={0}
            x2={0}
            y2={6}
            stroke="var(--card)"
            strokeWidth={2}
            opacity={0.5}
          />
        </pattern>
      </defs>

      {/* ── Rows ───────────────────────────────────────────── */}
      {bars.map((bar, idx) => {
        const y = padTop + idx * rowH;
        const barY = y + (rowH - barH) / 2;
        const x1 = toX(bar.start);
        const x2 = toX(bar.end);
        const barWidth = Math.max(x2 - x1, 4);
        const isBuy = bar.intent.side === "buy";
        const fillColor = isBuy ? "var(--success)" : "var(--destructive)";

        // Row separator
        const separator =
          idx > 0 ? (
            <line
              x1={0}
              x2={viewW}
              y1={y}
              y2={y}
              stroke="var(--border)"
              strokeWidth={0.3}
            />
          ) : null;

        return (
          <g key={bar.intent.instrument_id}>
            {separator}
            {/* Instrument label */}
            <text
              x={labelW - 6}
              y={barY + barH / 2 + 3}
              textAnchor="end"
              fontSize={9}
              fill="var(--foreground)"
              fontFamily="monospace"
            >
              {bar.intent.instrument_id.length > 12
                ? `${bar.intent.instrument_id.slice(0, 11)}…`
                : bar.intent.instrument_id}
            </text>
            {/* Bar */}
            <rect
              x={x1}
              y={barY}
              width={barWidth}
              height={barH}
              rx={3}
              fill={fillColor}
              opacity={0.75}
            />
            {/* Side badge inside bar */}
            {barWidth > 30 && (
              <text
                x={x1 + 5}
                y={barY + barH / 2 + 3}
                fontSize={7}
                fontWeight={600}
                fill="white"
              >
                {bar.intent.side.toUpperCase()} {bar.intent.quantity}
              </text>
            )}
          </g>
        );
      })}

      {/* ── Bottom border ──────────────────────────────────── */}
      <line
        x1={labelW}
        x2={viewW - padRight}
        y1={chartH - 12}
        y2={chartH - 12}
        stroke="var(--border)"
        strokeWidth={0.5}
      />
    </svg>
  );
}
