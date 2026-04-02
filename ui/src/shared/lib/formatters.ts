const priceFormatter = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 8,
});

const pnlFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  signDisplay: "exceptZero",
});

const quantityFormatter = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 8,
});

export function formatPrice(value: string): string {
  return priceFormatter.format(Number(value));
}

export function formatPnL(value: string): string {
  return pnlFormatter.format(Number(value));
}

export function formatQuantity(value: string): string {
  return quantityFormatter.format(Number(value));
}

export function formatTimestamp(iso: string): string {
  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(iso));
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(iso));
}

export function pnlColorClass(value: string): string {
  const n = Number(value);
  if (n > 0) return "text-green-600";
  if (n < 0) return "text-red-600";
  return "text-muted-foreground";
}
