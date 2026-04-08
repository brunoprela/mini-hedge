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
      <title>Line Chart</title>
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
  const fmt =
    formatValue ??
    ((v: number) =>
      v.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }));

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
            <span className="w-20 text-right font-mono" style={{ color }}>
              {isPositive ? "+" : ""}
              {fmt(item.value)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ─── Waterfall Chart ────────────────────────────────────────

interface WaterfallItem {
  label: string;
  value: number;
  isTotal?: boolean;
}

interface WaterfallChartProps {
  items: WaterfallItem[];
  height?: number;
  formatValue?: (v: number) => string;
}

export function WaterfallChart({ items, height = 200, formatValue }: WaterfallChartProps) {
  if (items.length === 0) {
    return <p className="text-sm text-[var(--muted-foreground)]">No data</p>;
  }

  const fmt = formatValue ?? ((v: number) => `${(v * 100).toFixed(2)}%`);

  // Compute running cumulative for positioning
  let cumulative = 0;
  const bars = items.map((item) => {
    if (item.isTotal) {
      const bar = { ...item, start: 0, end: item.value };
      cumulative = item.value;
      return bar;
    }
    const start = cumulative;
    cumulative += item.value;
    return { ...item, start, end: cumulative };
  });

  const allValues = bars.flatMap((b) => [b.start, b.end, 0]);
  const minVal = Math.min(...allValues);
  const maxVal = Math.max(...allValues);
  const range = maxVal - minVal || 1;

  const padTop = 20;
  const padBot = 40;
  const padLeft = 8;
  const padRight = 8;
  const viewW = 600;
  const chartH = height - padTop - padBot;
  const chartW = viewW - padLeft - padRight;
  const barW = (chartW / items.length) * 0.6;
  const gap = (chartW / items.length) * 0.4;

  function toY(v: number) {
    return padTop + chartH - ((v - minVal) / range) * chartH;
  }

  const zeroY = toY(0);

  return (
    <svg viewBox={`0 0 ${viewW} ${height}`} className="w-full" preserveAspectRatio="xMidYMid meet">
      <title>Bar Chart</title>
      {/* Zero line */}
      <line
        x1={padLeft}
        x2={viewW - padRight}
        y1={zeroY}
        y2={zeroY}
        stroke="var(--muted-foreground)"
        strokeWidth={0.5}
        strokeDasharray="4,3"
      />

      {bars.map((bar, i) => {
        const x = padLeft + i * (barW + gap) + gap / 2;
        const top = Math.min(toY(bar.start), toY(bar.end));
        const bottom = Math.max(toY(bar.start), toY(bar.end));
        const barH = Math.max(bottom - top, 1);
        const isPositive = bar.value >= 0;
        const fill = bar.isTotal
          ? "var(--primary)"
          : isPositive
            ? "var(--success)"
            : "var(--destructive)";

        // Connector line to next bar
        const connector =
          !bar.isTotal && i < bars.length - 1 ? (
            <line
              x1={x + barW}
              x2={x + barW + gap}
              y1={toY(bar.end)}
              y2={toY(bar.end)}
              stroke="var(--border)"
              strokeWidth={0.5}
              strokeDasharray="2,2"
            />
          ) : null;

        return (
          <g key={bar.label}>
            <rect x={x} y={top} width={barW} height={barH} rx={2} fill={fill} opacity={0.8} />
            {/* Value label */}
            <text
              x={x + barW / 2}
              y={isPositive || bar.isTotal ? top - 4 : bottom + 11}
              textAnchor="middle"
              fontSize={9}
              fontFamily="monospace"
              fill={fill}
            >
              {bar.isTotal ? "" : isPositive ? "+" : ""}
              {fmt(bar.value)}
            </text>
            {/* X label */}
            <text
              x={x + barW / 2}
              y={height - 4}
              textAnchor="middle"
              fontSize={8}
              fill="var(--muted-foreground)"
            >
              {bar.label}
            </text>
            {connector}
          </g>
        );
      })}
    </svg>
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
  const fmt =
    formatValue ??
    ((v: number) =>
      v.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }));
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
    <div className="flex flex-wrap items-center gap-3 rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2">
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

// ─── Donut Chart ───────────────────────────────────────────

interface DonutSegment {
  label: string;
  value: number;
  color: string;
}

interface DonutChartProps {
  segments: DonutSegment[];
  size?: number;
  thickness?: number;
  centerLabel?: string;
  centerValue?: string;
}

const DONUT_PALETTE = [
  "var(--primary)",
  "var(--success)",
  "var(--warning)",
  "var(--destructive)",
  "var(--accent-orange)",
  "#6366f1",
  "#06b6d4",
  "#8b5cf6",
  "#ec4899",
  "#14b8a6",
];

export function DonutChart({
  segments,
  size = 180,
  thickness = 32,
  centerLabel,
  centerValue,
}: DonutChartProps) {
  const total = segments.reduce((acc, s) => acc + s.value, 0);
  if (total === 0) {
    return <p className="text-sm text-[var(--muted-foreground)]">No data</p>;
  }

  const r = (size - thickness) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * r;

  let accumulated = 0;

  return (
    <div className="flex flex-col items-center gap-3">
      <svg viewBox={`0 0 ${size} ${size}`} className="w-full max-w-[240px]">
        <title>Donut Chart</title>
        {segments.map((seg, i) => {
          const pct = seg.value / total;
          const dashLen = pct * circumference;
          const dashOffset = -accumulated * circumference;
          accumulated += pct;

          return (
            <circle
              key={seg.label}
              cx={cx}
              cy={cy}
              r={r}
              fill="none"
              stroke={seg.color || DONUT_PALETTE[i % DONUT_PALETTE.length]}
              strokeWidth={thickness}
              strokeDasharray={`${dashLen} ${circumference - dashLen}`}
              strokeDashoffset={dashOffset}
              transform={`rotate(-90 ${cx} ${cy})`}
            />
          );
        })}
        {/* Center text */}
        {(centerValue || centerLabel) && (
          <>
            {centerValue && (
              <text
                x={cx}
                y={centerLabel ? cy - 4 : cy + 4}
                textAnchor="middle"
                fontSize={22}
                fontWeight="bold"
                fontFamily="monospace"
                fill="var(--foreground)"
              >
                {centerValue}
              </text>
            )}
            {centerLabel && (
              <text
                x={cx}
                y={centerValue ? cy + 14 : cy + 4}
                textAnchor="middle"
                fontSize={9}
                fill="var(--muted-foreground)"
              >
                {centerLabel}
              </text>
            )}
          </>
        )}
      </svg>

      {/* Legend */}
      <div className="flex flex-wrap justify-center gap-x-4 gap-y-1">
        {segments.map((seg, i) => (
          <div key={seg.label} className="flex items-center gap-1.5 text-xs">
            <span
              className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{ backgroundColor: seg.color || DONUT_PALETTE[i % DONUT_PALETTE.length] }}
            />
            <span className="text-[var(--muted-foreground)]">{seg.label}</span>
            <span className="font-mono font-medium text-[var(--foreground)]">
              {((seg.value / total) * 100).toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Mini Bar Chart (Sparkline-style vertical bars) ────────

interface MiniBarChartProps {
  data: number[];
  height?: number;
  width?: number;
  color?: string;
  negativeColor?: string;
}

export function MiniBarChart({
  data,
  height = 40,
  width = 120,
  color = "var(--primary)",
  negativeColor = "var(--destructive)",
}: MiniBarChartProps) {
  if (data.length === 0) return null;

  const max = Math.max(...data.map(Math.abs), 1);
  const barW = Math.max((width / data.length) * 0.7, 2);
  const gap = (width / data.length) * 0.3;
  const mid = height / 2;
  const hasNeg = data.some((d) => d < 0);
  const baseline = hasNeg ? mid : height;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <title>Sparkline Chart</title>
      {data.map((v, i) => {
        const barH = hasNeg
          ? (Math.abs(v) / max) * (height / 2 - 2)
          : (Math.abs(v) / max) * (height - 4);
        const x = i * (barW + gap);
        const y = v >= 0 ? baseline - barH : baseline;

        return (
          <rect
            // biome-ignore lint/suspicious/noArrayIndexKey: chart data points
            key={i}
            x={x}
            y={y}
            width={barW}
            height={Math.max(barH, 1)}
            rx={1}
            fill={v >= 0 ? color : negativeColor}
            opacity={0.8}
          />
        );
      })}
      {hasNeg && (
        <line x1={0} x2={width} y1={mid} y2={mid} stroke="var(--border)" strokeWidth={0.5} />
      )}
    </svg>
  );
}
