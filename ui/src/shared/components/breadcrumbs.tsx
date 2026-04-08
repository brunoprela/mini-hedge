"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Fragment } from "react";
import { useFundContext } from "@/shared/hooks/use-fund-context";

const SEGMENT_LABELS: Record<string, string> = {
  portfolio: "Portfolios",
  orders: "Orders",
  exposure: "Exposure",
  risk: "Risk",
  compliance: "Compliance",
  cash: "Cash",
  attribution: "Attribution",
  alpha: "Alpha",
  investors: "Investors",
  "fx-hedging": "FX Hedging",
  eod: "EOD & NAV",
  fees: "Fees",
  instruments: "Instruments",
  "market-data": "Market Data",
  settings: "Settings",
};

function isUuidOrId(segment: string): boolean {
  return /^[0-9a-f]{8}-/.test(segment) || /^\d+$/.test(segment);
}

export function Breadcrumbs() {
  const pathname = usePathname();
  const { fundSlug } = useFundContext();

  const prefix = `/${fundSlug}`;
  const relativePath = pathname.startsWith(prefix) ? pathname.slice(prefix.length) : pathname;

  const parts = relativePath.split("/").filter(Boolean);

  if (parts.length === 0) return null;

  const segments = parts
    .filter((part) => !isUuidOrId(part))
    .map((part, i, arr) => ({
      label: SEGMENT_LABELS[part] ?? part,
      path: `/${fundSlug}/${arr.slice(0, i + 1).join("/")}`,
    }));

  if (segments.length === 0) return null;

  return (
    <nav className="flex items-center gap-1.5 text-sm text-[var(--muted-foreground)] mb-4">
      <Link href={`/${fundSlug}`} className="hover:text-[var(--foreground)]">
        Dashboard
      </Link>
      {segments.map((seg, i) => (
        <Fragment key={seg.path}>
          <span>/</span>
          {i === segments.length - 1 ? (
            <span className="text-[var(--foreground)] font-medium">{seg.label}</span>
          ) : (
            <Link href={seg.path} className="hover:text-[var(--foreground)]">
              {seg.label}
            </Link>
          )}
        </Fragment>
      ))}
    </nav>
  );
}
