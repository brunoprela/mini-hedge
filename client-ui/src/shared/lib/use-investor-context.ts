"use client";

/**
 * useInvestorContext — per-fund investor context loader.
 *
 * Resolves the current investor's id, active capital account, KYC status, and
 * fund terms for a given fund slug. The backend currently exposes "investors
 * for this fund" via `/api/v1/capital/investors` (scoped by X-Fund-Slug header)
 * and treats the first returned record as the caller's investor record —
 * mirroring the pattern used elsewhere in client-ui (`funds/page.tsx`,
 * `page.tsx`). If/when the backend grows a dedicated `/api/v1/me/investor`
 * endpoint we can swap to that here without touching callers.
 */

import { useQuery } from "@tanstack/react-query";
import { api, fundHeaders } from "@/shared/lib/api-client";
import type { CapitalAccountSummary, FundTermsSummary, InvestorInfo } from "@/shared/types";

export interface InvestorContext {
  investor: InvestorInfo | null;
  accounts: CapitalAccountSummary[];
  fundTerms: FundTermsSummary[];
  // Flattened convenience values for the common default share class.
  primaryAccount: CapitalAccountSummary | null;
  primaryTerms: FundTermsSummary | null;
  // Latest NAV per share (USD) if available — used for estimated shares.
  navPerShare: number | null;
}

export function useInvestorContext(fundSlug: string | null | undefined) {
  return useQuery<InvestorContext>({
    queryKey: ["investor-context", fundSlug],
    enabled: !!fundSlug,
    queryFn: async () => {
      if (!fundSlug) {
        return {
          investor: null,
          accounts: [],
          fundTerms: [],
          primaryAccount: null,
          primaryTerms: null,
          navPerShare: null,
        };
      }

      // Investors accessible to this caller within the fund.
      const { data: investorsData, error: investorsError } = await api.GET(
        "/api/v1/capital/investors",
        { headers: fundHeaders(fundSlug) },
      );
      if (investorsError) throw investorsError;
      const investors: InvestorInfo[] = investorsData ?? [];
      const investor = investors[0] ?? null;

      let accounts: CapitalAccountSummary[] = [];
      if (investor) {
        const { data: accountsData, error: accountsError } = await api.GET(
          "/api/v1/capital/investors/{investor_id}/history",
          {
            params: { path: { investor_id: investor.id } },
            headers: fundHeaders(fundSlug),
          },
        );
        if (accountsError) throw accountsError;
        accounts = accountsData ?? [];
      }

      // Fund terms are listed globally; filter client-side. The endpoint is
      // fund-scoped via the X-Fund-Slug header used by the BFF proxy.
      const { data: fundTermsData, error: fundTermsError } = await api.GET(
        "/api/v1/investor-operations/fund-terms",
        { headers: fundHeaders(fundSlug) },
      );
      if (fundTermsError) throw fundTermsError;
      const fundTerms: FundTermsSummary[] = fundTermsData ?? [];

      // Latest NAV per share from EOD NAV history (short lookback so it's
      // cheap). Note this is the fund-level NAV, not per share class.
      let navPerShare: number | null = null;
      try {
        const { data, error } = await api.GET("/api/v1/eod/nav/history", {
          params: { query: { period: "30d" } },
          headers: fundHeaders(fundSlug),
        });
        if (!error && data && data.length > 0) {
          const latest = [...data].sort((a, b) =>
            b.business_date.localeCompare(a.business_date),
          )[0];
          navPerShare = Number(latest.nav_per_share) || null;
        }
      } catch {
        navPerShare = null;
      }

      const primaryAccount = accounts[0] ?? null;
      const primaryShareClass = primaryAccount?.share_class ?? "default";
      const primaryTerms =
        fundTerms.find((t) => t.share_class === primaryShareClass) ?? fundTerms[0] ?? null;

      return {
        investor,
        accounts,
        fundTerms,
        primaryAccount,
        primaryTerms,
        navPerShare,
      };
    },
  });
}
