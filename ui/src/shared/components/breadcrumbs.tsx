"use client";

/**
 * Fund-scoped breadcrumbs for the desk UI.
 *
 * Thin adapter over `@mini-hedge/ui`'s shared {@link Breadcrumbs} primitive that
 * plugs in the fund-slug path prefix and our segment-label dictionary.
 */

import { Breadcrumbs as SharedBreadcrumbs } from "@mini-hedge/ui";
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

export function Breadcrumbs() {
  const { fundSlug } = useFundContext();
  return (
    <SharedBreadcrumbs
      segmentLabels={SEGMENT_LABELS}
      rootLabel="Dashboard"
      rootHref={`/${fundSlug}`}
      pathPrefix={`/${fundSlug}`}
      className="mb-4"
    />
  );
}
