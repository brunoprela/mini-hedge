"use client";

/**
 * Lightweight SVG chart components — no external dependencies.
 */

// ─── Line Chart ─────────────────────────────────────────────

interface LineChartSeries {
  data: { x: string; y: number }[];
  color: string;
  label?: string;
  dashed?: boolean;
}

interface LineChartProps {
  series: LineChartSeries[];
  height?: number;
  showXLabels?: boolean;
  xLabelInterval?: number;
  formatY?: (v: number) => string;
}

export function LineChart({
  series,
  height = 200,
  showXLabels = true,
  xLabelInterval = 5,
  formatY,
}: LineChartProps) {
  if (series.length === 0 || series[0].data.length < 2) {
    return <p className="text-sm text-[var(--muted-foreground)]">Not enough data</p>;
  }

  const allY = series.flatMap((s) => s.data.map((d) => d.y));
  const minY = Math.min(...allY);
  const maxY = Math.max(...allY);
  const rangeY = maxY - minY || 1;

  const padTop = 16;
  const padBot = showXLabels ? 28 : 8;
  const padLeft = 52;
  const padRight = 12;
  const chartH = height - padTop - padBot;

  const maxLen = Math.max(...series.map((s) => s.data.length));
  const viewW = 600;
  const chartW = viewW - padLeft - padRight;

  function toX(i: number) {
    return padLeft + (i / (maxLen - 1)) * chartW;
  }
  function toY(v: number) {
    return padTop + chartH - ((v - minY) / rangeY) * chartH;
  }

  // Y-axis labels (5 ticks)
  const yTicks = Array.from({ length: 5 }, (_, i) => minY + (rangeY * i) / 4);
  const fmtY = formatY ?? ((v: number) => v.toFixed(2));

  // Zero line position (if range crosses zero)
  const showZero = minY < 0 && maxY > 0;

  return (
    <svg viewBox={`0 0 ${viewW} ${height}`} className="w-full" preserveAspectRatio="xMidYMid meet">
      {/* Grid lines */}
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
            fill="var(--muted-foreground)"
          >
            {fmtY(tick)}
          </text>
        </g>
      ))}

      {/* Zero line */}
      {showZero && (
        <line
          x1={padLeft}
          x2={viewW - padRight}
          y1={toY(0)}
          y2={toY(0)}
          stroke="var(--muted-foreground)"
          strokeWidth={0.5}
          strokeDasharray="4,3"
        />
      )}

      {/* Series */}
      {series.map((s) => {
        const points = s.data.map((d, i) => `${toX(i)},${toY(d.y)}`).join(" ");
        return (
          <polyline
            key={s.label ?? s.color}
            points={points}
            fill="none"
            stroke={s.color}
            strokeWidth={1.5}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray={s.dashed ? "6,3" : undefined}
          />
        );
      })}

      {/* X-axis labels */}
      {showXLabels &&
        series[0].data.map((d, i) => {
          if (i % xLabelInterval !== 0 && i !== series[0].data.length - 1) return null;
          return (
            <text
              key={d.x}
              x={toX(i)}
              y={height - 4}
              textAnchor="middle"
              fontSize={8}
              fill="var(--muted-foreground)"
            >
              {d.x.slice(5)}
            </text>
          );
        })}

      {/* Legend */}
      {series.length > 1 &&
        series.map((s, i) => (
          <g key={s.label ?? i}>
            <line
              x1={padLeft + i * 100}
              x2={padLeft + i * 100 + 16}
              y1={6}
              y2={6}
              stroke={s.color}
              strokeWidth={2}
              strokeDasharray={s.dashed ? "4,2" : undefined}
            />
            <text x={padLeft + i * 100 + 20} y={9} fontSize={9} fill="var(--muted-foreground)">
              {s.label}
            </text>
          </g>
        ))}
    </svg>
  );
}

// ─── Horizontal Bar Chart (Top/Bottom Movers) ───────────────

interface BarChartItem {
  label: string;
  value: number;
  color?: string;
}

interface HBarChartProps {
  items: BarChartItem[];
  formatValue?: (v: number) => string;
}

export function HBarChart({ items, formatValue }: HBarChartProps) {
  if (items.length === 0) {
    return <p className="text-sm text-[var(--muted-foreground)]">No data</p>;
  }

  const maxAbs = Math.max(...items.map((i) => Math.abs(i.value)), 1);
  const fmt = formatValue ?? ((v: number) => v.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }));

  return (
    <div className="space-y-1.5">
      {items.map((item) => {
        const pct = (Math.abs(item.value) / maxAbs) * 100;
        const isPositive = item.value >= 0;
        const color = item.color ?? (isPositive ? "var(--success)" : "var(--destructive)");

        return (
          <div key={item.label} className="flex items-center gap-2 text-xs">
            <span className="w-16 truncate text-right font-mono text-[var(--foreground)]">
              {item.label}
            </span>
            <div className="flex-1">
              <div
                className="h-4 rounded-sm"
                style={{
                  width: `${Math.max(pct, 2)}%`,
                  backgroundColor: color,
                  opacity: 0.75,
                }}
              />
            </div>
            <span
              className="w-20 text-right font-mono"
              style={{ color }}
            >
              {isPositive ? "+" : ""}{fmt(item.value)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ─── Gauge Bar ──────────────────────────────────────────────

interface GaugeBarProps {
  value: number;
  max: number;
  label?: string;
  formatValue?: (v: number) => string;
  formatMax?: (v: number) => string;
}

export function GaugeBar({ value, max, label, formatValue, formatMax }: GaugeBarProps) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  const fmt = formatValue ?? ((v: number) =>
    v.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 })
  );
  const fmtMax = formatMax ?? fmt;

  let barColor = "var(--success)";
  if (pct > 80) barColor = "var(--destructive)";
  else if (pct > 60) barColor = "var(--warning)";

  return (
    <div>
      {label && (
        <div className="mb-1 flex items-center justify-between text-xs text-[var(--muted-foreground)]">
          <span>{label}</span>
          <span>
            {fmt(value)} / {fmtMax(max)}
          </span>
        </div>
      )}
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-[var(--border)]">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: barColor }}
        />
      </div>
      <p className="mt-0.5 text-right text-[10px] text-[var(--muted-foreground)]">
        {pct.toFixed(0)}% utilized
      </p>
    </div>
  );
}

// ─── Status Dot ─────────────────────────────────────────────

type DotVariant = "success" | "warning" | "error" | "info" | "neutral";

const DOT_COLORS: Record<DotVariant, string> = {
  success: "bg-[var(--success)]",
  warning: "bg-[var(--warning)]",
  error: "bg-[var(--destructive)]",
  info: "bg-[var(--primary)]",
  neutral: "bg-[var(--muted-foreground)]",
};

export function StatusDot({ variant, size = 8 }: { variant: DotVariant; size?: number }) {
  return (
    <span
      className={`inline-block shrink-0 rounded-full ${DOT_COLORS[variant]}`}
      style={{ width: size, height: size }}
    />
  );
}

// ─── Summary Strip ──────────────────────────────────────────

interface SummaryStripItem {
  label: string;
  value: string;
  color?: string;
}

export function SummaryStrip({ items }: { items: SummaryStripItem[] }) {
  return (
    <div className="flex flex-wrap items-center gap-6 rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-3">
      {items.map((item) => (
        <div key={item.label}>
          <p className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">
            {item.label}
          </p>
          <p
            className="font-mono text-sm font-semibold"
            style={item.color ? { color: item.color } : undefined}
          >
            {item.value}
          </p>
        </div>
      ))}
    </div>
  );
}
